"""
Post Image Generator for BIP System

Generates images for social media posts using Gemini Imagen 3 API.
Based on ASOP-WCC image generation architecture.

Features:
- Automatic image prompt extraction from post content
- Platform-specific image dimensions
- Gemini Imagen 3 with fallbacks
- Brand-consistent styling
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.config import settings, bip_settings


# Supported image extensions
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp']

# Base brand guidelines (applied to all styles)
# This can be customized in config/bip_settings.yaml
BIP_BRAND_BASE = """
Brand: Build-in-Public indie developer content
Quality: High resolution, sharp details, professional finish
Constraints:
- No text overlay or watermarks (text added separately)
- No human faces or identifiable persons
- No placeholder text like "lorem ipsum"
- Suitable for social media (Xiaohongshu, Twitter, LinkedIn)
"""


def get_platform_dimensions(platform: str) -> Tuple[int, int]:
    """Get image dimensions for a platform from config."""
    dims = bip_settings.get_platform_dimensions(platform)
    return (dims.get("width", 1200), dims.get("height", 675))


class ImageGenerator:
    """Generate images for social media posts."""

    def __init__(self):
        """Initialize the image generator."""
        self.base_dir = Path(settings.base_dir)
        self.temp_posts_dir = self.base_dir / "data" / "temp_posts"
        self.selected_posts_dir = self.base_dir / "data" / "selected_posts"
        self.post_images_dir = self.base_dir / "data" / "post-images"

        # Image generation marker
        self.images_ready_marker = "images.ready"

        # Image generation clients (fallback chain: Vertex AI -> Gemini API -> OpenAI)
        self.gemini_client = None
        self.openai_client = None
        self.use_vertex_ai = False
        self._init_image_clients()

    def _init_image_clients(self):
        """Initialize image generation clients.

        Fallback chain:
        1. Gemini 3 Pro Preview (best quality, generate_content API)
        2. Gemini 2.5 Flash Image (fast, generate_content API)
        3. OpenAI DALL-E 3 (final fallback)

        Note: Imagen models (generate_images API) are restricted and not used.
        """
        # Initialize Gemini client for image generation
        if settings.gemini_api_key:
            try:
                from google import genai

                # Use default API version for generate_content with image modality
                self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
                print("  ✅ Gemini image generation initialized (gemini-3-pro-image-preview)")

            except ImportError:
                print("  ⚠️  google-genai package not installed. Run: pip install google-genai")
            except Exception as e:
                print(f"  ⚠️  Gemini initialization failed: {e}")

        # Try to initialize OpenAI DALL-E (final fallback)
        if settings.openai_api_key:
            try:
                import httpx
                from openai import OpenAI

                http_client = httpx.Client(proxy=None)
                self.openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    http_client=http_client
                )
                print("  ✅ OpenAI DALL-E 3 initialized (fallback)")

            except ImportError:
                print("  ⚠️  openai package not installed for DALL-E fallback")
            except Exception as e:
                print(f"  ⚠️  OpenAI DALL-E initialization failed: {e}")

        # Check if any image generation is available
        if not self.gemini_client and not self.openai_client:
            print("  ⚠️  No image generation API configured - image generation disabled")
            print("     Configure GEMINI_API_KEY or OPENAI_API_KEY in .env")

    def extract_image_prompts_from_post(self, post_content: str, topic: str = "") -> List[Dict[str, str]]:
        """
        Extract image generation prompts from post content.

        Looks for:
        1. Explicit ## Image Prompts section
        2. Key themes and visual concepts from content

        Args:
            post_content: The post markdown content
            topic: Topic/theme of the post (optional)

        Returns:
            List of prompt dictionaries with 'name' and 'prompt' keys
        """
        prompts = []

        # First, check for explicit image prompts section
        if "## Image Prompts" in post_content or "## 图片生成提示" in post_content:
            prompts.extend(self._extract_explicit_prompts(post_content))

        # If no explicit prompts, generate from content analysis
        if not prompts:
            prompts.append(self._generate_prompt_from_content(post_content, topic))

        return prompts

    def _extract_explicit_prompts(self, content: str) -> List[Dict[str, str]]:
        """Extract explicitly marked image prompts from content."""
        prompts = []

        # Find image prompts section
        for header in ["## Image Prompts", "## 图片生成提示"]:
            if header in content:
                parts = content.split(header)
                if len(parts) >= 2:
                    prompts_section = parts[1]

                    # Stop at next section
                    if "\n## " in prompts_section:
                        prompts_section = prompts_section.split("\n## ")[0]

                    # Extract code blocks as prompts
                    pattern = r'###\s+(.+?)\n```\n(.+?)\n```'
                    matches = re.findall(pattern, prompts_section, re.DOTALL)

                    for name, prompt in matches:
                        prompts.append({
                            "name": name.strip(),
                            "prompt": prompt.strip()
                        })

                    # If no code blocks, use the whole section as one prompt
                    if not prompts and prompts_section.strip():
                        prompts.append({
                            "name": "cover",
                            "prompt": prompts_section.strip()
                        })
                break

        return prompts

    def _detect_post_type(self, content: str) -> str:
        """
        Detect the type of post based on content analysis.

        Args:
            content: The post content

        Returns:
            Post type string (e.g., 'technical', 'story', 'productivity')
        """
        scores = {}

        for post_type, keywords in bip_settings.post_type_keywords.items():
            score = 0
            for keyword in keywords:
                matches = re.findall(keyword, content, re.IGNORECASE)
                score += len(matches)
            scores[post_type] = score

        # Get the type with highest score
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 0:
                return best_type

        return "default"

    def _extract_literal_subject(self, content: str, topic: str) -> str:
        """
        Extract the literal/concrete subject matter from the post.

        Instead of abstract concepts, identify what should actually be shown.

        Args:
            content: The post content
            topic: The topic/folder name

        Returns:
            A concrete description of what the image should depict
        """
        # Extract the main subject - first meaningful line or title
        lines = content.split('\n')
        main_subject = topic

        for line in lines:
            line = line.strip()
            # Skip metadata, headers, empty lines
            if not line or line.startswith('#') or line.startswith('---'):
                continue
            if len(line) > 10:
                main_subject = line[:100]
                break

        # Look for specific objects/tools mentioned
        concrete_items = []

        # Tools and software
        tool_matches = re.findall(
            r'(Claude Code|Claude|ChatGPT|Gemini|Notion|Figma|VS Code|Terminal|'
            r'Python|JavaScript|API|数据库|服务器|手机|电脑|日历|笔记本|'
            r'Telegram|微信|小红书|Twitter|浏览器|编辑器)',
            content, re.IGNORECASE
        )
        concrete_items.extend(set(tool_matches))

        # Actions being described
        action_matches = re.findall(
            r'(写代码|coding|发布|posting|规划|planning|自动化|automating|'
            r'分析|analyzing|设计|designing|测试|testing|部署|deploying)',
            content, re.IGNORECASE
        )
        concrete_items.extend(set(action_matches))

        return {
            "main_subject": main_subject,
            "concrete_items": concrete_items[:5]
        }

    def _generate_prompt_from_content(self, content: str, topic: str = "") -> Dict[str, str]:
        """
        Generate an image prompt based on post content analysis.

        Creates literal, concrete visual descriptions based on post type.
        """
        # Detect post type
        post_type = self._detect_post_type(content)
        style_config = bip_settings.post_type_styles.get(post_type, bip_settings.post_type_styles.get("default", ""))

        # Extract literal subject matter
        subject_info = self._extract_literal_subject(content, topic)
        main_subject = subject_info["main_subject"]
        concrete_items = subject_info["concrete_items"]

        # Build concrete visual description based on post type
        if post_type == "technical":
            visual_scene = f"""A clean technical diagram showing:
- Main concept: {main_subject}
- Visual elements: {', '.join(concrete_items) if concrete_items else 'code editor, terminal window, system architecture'}
- Show actual workflow connections, data flow arrows, or system components
- Include recognizable developer tools like terminal, code blocks, or API endpoints"""

        elif post_type == "story":
            visual_scene = f"""A warm illustrated scene depicting:
- The moment/situation: {main_subject}
- Setting: a cozy workspace or relevant environment
- Show the emotional context of the story
- Include subtle details that make the scene feel personal and authentic"""

        elif post_type == "tool_review":
            visual_scene = f"""A product-focused visualization showing:
- The tool/product being discussed: {main_subject}
- Display: UI mockups, feature comparisons, or product interfaces
- Items to show: {', '.join(concrete_items) if concrete_items else 'software interface, comparison chart'}
- Clean, professional product photography style"""

        elif post_type == "productivity":
            visual_scene = f"""An isometric workspace illustration showing:
- The productivity concept: {main_subject}
- Include: organized desk, calendar, task lists, or workflow tools
- Show: {', '.join(concrete_items) if concrete_items else 'planner, clock, checklist, organized workspace'}
- Convey efficiency and organization through visual arrangement"""

        elif post_type == "announcement":
            visual_scene = f"""A celebratory announcement graphic showing:
- The achievement: {main_subject}
- Include milestone indicators, achievement badges, or launch visuals
- Elements: {', '.join(concrete_items) if concrete_items else 'celebration confetti, milestone number, rocket launch'}
- Bold, attention-grabbing composition"""

        elif post_type == "reflection":
            visual_scene = f"""A thoughtful minimalist illustration showing:
- The concept: {main_subject}
- Use meaningful symbolism that represents the insight
- Include: lightbulb, contemplative scene, or metaphorical imagery
- Elegant, simple composition with focus on the central idea"""

        else:
            visual_scene = f"""A professional illustration showing:
- Topic: {main_subject}
- Include literal representations of: {', '.join(concrete_items) if concrete_items else 'relevant objects and tools'}
- Show the actual subject matter, not abstract concepts
- Clear, direct visual communication"""

        prompt = f"""Create a social media image for this Build-in-Public post:

SUBJECT: {topic or main_subject}

SCENE TO DEPICT:
{visual_scene}

STYLE REQUIREMENTS:
- Style: {style_config['style']}
- Rendering: {style_config['rendering']}
- Color approach: {style_config['color_approach']}

IMPORTANT:
- Make the image LITERAL and CONCRETE - show actual objects/scenes, not abstract concepts
- The viewer should immediately understand what the post is about from the image
- No text, no faces, no placeholder content

{BIP_BRAND_BASE}
"""

        print(f"    📊 Detected post type: {post_type}")

        return {
            "name": "cover",
            "prompt": prompt
        }

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Convert dimensions to Imagen API aspect ratio string."""
        ratio = width / height

        if abs(ratio - 1.0) < 0.1:
            return "1:1"
        elif abs(ratio - 0.75) < 0.1:  # 3:4
            return "3:4"
        elif abs(ratio - 1.33) < 0.1:  # 4:3
            return "4:3"
        elif abs(ratio - 0.5625) < 0.1:  # 9:16
            return "9:16"
        elif abs(ratio - 1.78) < 0.1:  # 16:9
            return "16:9"
        elif ratio < 1:
            return "3:4"  # Default vertical
        else:
            return "16:9"  # Default horizontal

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        image_name: str,
        width: int = 1080,
        height: int = 1440,
        platform: str = "xiaohongshu"
    ) -> Dict[str, Any]:
        """
        Generate an image using Gemini image generation models.

        Fallback chain:
        1. Gemini 3 Pro Preview (best quality)
        2. Gemini 2.5 Flash Image (fast)
        3. OpenAI DALL-E 3 (final fallback)

        Args:
            prompt: Image generation prompt
            output_path: Directory to save the image
            image_name: Name for the output image file (without extension)
            width: Image width in pixels
            height: Image height in pixels
            platform: Target platform

        Returns:
            Dictionary with success status and file path or error
        """
        if not self.gemini_client and not self.openai_client:
            return {
                "success": False,
                "error": "No image generation API configured. Set GEMINI_API_KEY or OPENAI_API_KEY."
            }

        # Primary: Try Gemini 3 Pro Preview (best quality)
        if self.gemini_client:
            result = self._generate_with_gemini_model(
                prompt, output_path, image_name, width, height, platform,
                model="gemini-3-pro-image-preview"
            )
            if result.get("success"):
                return result

            # Fallback: Try Gemini 2.5 Flash Image (faster)
            print(f"    🔄 Trying Gemini 2.5 Flash Image fallback...")
            result = self._generate_with_gemini_model(
                prompt, output_path, image_name, width, height, platform,
                model="gemini-2.5-flash-preview-05-20"
            )
            if result.get("success"):
                return result

        # Final fallback: OpenAI DALL-E 3
        if self.openai_client:
            print(f"    🔄 Trying OpenAI DALL-E 3 fallback...")
            return self._generate_with_openai_dalle(
                prompt, output_path, image_name, width, height
            )

        return {
            "success": False,
            "error": "All image generation providers failed"
        }

    def _generate_with_gemini_model(
        self,
        prompt: str,
        output_path: Path,
        image_name: str,
        width: int,
        height: int,
        platform: str,
        model: str = "gemini-3-pro-image-preview"
    ) -> Dict[str, Any]:
        """
        Generate image using Gemini models with generate_content API.

        Args:
            prompt: Image generation prompt
            output_path: Directory to save the image
            image_name: Name for the output image file
            width: Image width in pixels
            height: Image height in pixels
            platform: Target platform
            model: Gemini model to use

        Returns:
            Dictionary with success status and file path or error
        """
        try:
            import base64
            from google.genai import types

            # Enhance prompt with brand guidelines
            enhanced_prompt = f"""Generate an image with the following specifications:

{prompt}

{BIP_BRAND_BASE}
Target dimensions: {width}x{height} pixels
Platform: {platform}

Please generate this image."""

            # Use generate_content with image modality
            response = self.gemini_client.models.generate_content(
                model=model,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE'],
                )
            )

            # Extract image from response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        if part.inline_data.mime_type.startswith('image/'):
                            raw_data = part.inline_data.data

                            # Detect format and decode if needed
                            image_data = self._decode_image_data(raw_data)

                            output_path.mkdir(parents=True, exist_ok=True)
                            image_path = output_path / f"{image_name}.png"

                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            return {
                                "success": True,
                                "file_path": str(image_path),
                                "dimensions": f"{width}x{height}",
                                "model": model
                            }

            return {
                "success": False,
                "error": f"{model} did not return an image"
            }

        except Exception as e:
            error_msg = str(e)
            print(f"    ⚠️  {model} failed: {error_msg}")
            return {
                "success": False,
                "error": f"{model} error: {error_msg}"
            }

    def _decode_image_data(self, raw_data) -> bytes:
        """
        Decode image data from various formats.

        The Gemini API can return image data in different formats:
        - Raw bytes (direct binary data)
        - Base64-encoded string
        - Base64-encoded bytes

        Returns:
            Decoded image bytes
        """
        import base64

        # PNG starts with: 0x89 0x50 0x4E 0x47 (‰PNG)
        # JPEG starts with: 0xFF 0xD8 0xFF
        # GIF starts with: 0x47 0x49 0x46 (GIF)
        valid_headers = [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'GIF8']

        if isinstance(raw_data, str):
            # Data is base64-encoded string
            return base64.b64decode(raw_data)
        elif isinstance(raw_data, bytes):
            # Check if it's already raw image data
            if raw_data[:4] in valid_headers:
                return raw_data
            else:
                # Try base64 decoding
                try:
                    decoded = base64.b64decode(raw_data)
                    # Verify decoded data is valid image
                    if decoded[:4] in valid_headers:
                        return decoded
                    else:
                        # Decoding produced non-image data, use original
                        return raw_data
                except Exception:
                    # Not base64 encoded, use as-is
                    return raw_data
        else:
            return raw_data

    def _generate_with_openai_dalle(
        self,
        prompt: str,
        output_path: Path,
        image_name: str,
        width: int,
        height: int
    ) -> Dict[str, Any]:
        """
        Fallback: Generate image using OpenAI DALL-E 3.
        """
        if not self.openai_client:
            return {
                "success": False,
                "error": "OpenAI client not initialized"
            }

        try:
            import base64

            # Enhance prompt with brand guidelines
            enhanced_prompt = f"""{prompt}

{BIP_BRAND_BASE}
Style: Professional, clean, modern digital illustration suitable for social media.
"""

            # Determine size (DALL-E 3 supports: 1024x1024, 1792x1024, 1024x1792)
            ratio = width / height
            if ratio > 1.5:  # Wide/landscape
                size = "1792x1024"
            elif ratio < 0.67:  # Tall/portrait
                size = "1024x1792"
            else:  # Square-ish
                size = "1024x1024"

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt[:4000],  # DALL-E 3 has 4000 char limit
                size=size,
                quality="standard",
                n=1,
                response_format="b64_json"
            )

            if response.data and response.data[0].b64_json:
                # Decode and save image
                image_data = base64.b64decode(response.data[0].b64_json)
                output_path.mkdir(parents=True, exist_ok=True)
                image_path = output_path / f"{image_name}.png"

                with open(image_path, 'wb') as f:
                    f.write(image_data)

                return {
                    "success": True,
                    "file_path": str(image_path),
                    "dimensions": size,
                    "model": "dall-e-3"
                }
            else:
                return {
                    "success": False,
                    "error": "DALL-E 3 did not return an image"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"DALL-E 3 error: {str(e)}"
            }

    def check_image_exists(self, folder: Path, image_name: str) -> Optional[str]:
        """Check if an image already exists in the folder."""
        if not folder.exists():
            return None

        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            image_path = folder / f"{image_name}{ext}"
            if image_path.exists():
                return str(image_path)

        return None

    def generate_images_for_post(
        self,
        post_folder: Path,
        platform: str = "xiaohongshu",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Generate images for a specific post folder.

        Args:
            post_folder: Path to the post folder (temp_posts/xxx or selected_posts/xxx)
            platform: Target platform
            force: Force regeneration even if images exist

        Returns:
            Results dictionary
        """
        results = {
            "folder": str(post_folder),
            "platform": platform,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "images": []
        }

        # Check if images already generated
        images_marker = post_folder / self.images_ready_marker
        if images_marker.exists() and not force:
            results["skipped"] = 1
            results["message"] = "Images already generated (images.ready exists)"
            return results

        topic = post_folder.name
        prompts = []

        # Priority 1: Look for separate image-prompt.md file
        image_prompt_file = post_folder / "image-prompt.md"
        if image_prompt_file.exists():
            try:
                with open(image_prompt_file, 'r', encoding='utf-8') as f:
                    prompt_content = f.read()
                prompts = self.extract_image_prompts_from_post(prompt_content, topic)
                if prompts:
                    print(f"    📄 Using prompts from: image-prompt.md")
            except Exception as e:
                print(f"    ⚠️  Failed to read image-prompt.md: {e}")

        # Priority 2: Fall back to extracting from post.md
        if not prompts:
            post_file = None
            for name in ["post.md", "post_链接内容无法获取.md"]:
                candidate = post_folder / name
                if candidate.exists():
                    post_file = candidate
                    break

            if not post_file:
                results["message"] = "No post.md or image-prompt.md found in folder"
                return results

            # Read post content
            try:
                with open(post_file, 'r', encoding='utf-8') as f:
                    post_content = f.read()
            except Exception as e:
                results["message"] = f"Failed to read post: {e}"
                return results

            # Extract image prompts from post content
            prompts = self.extract_image_prompts_from_post(post_content, topic)
            if prompts:
                print(f"    📄 Using prompts from: {post_file.name}")

        if not prompts:
            results["message"] = "No image prompts extracted"
            return results

        # Get dimensions for platform
        width, height = get_platform_dimensions(platform)

        # Create images output folder
        images_folder = post_folder / "images"

        for prompt_info in prompts:
            image_name = prompt_info["name"].lower().replace(" ", "_")
            image_name = re.sub(r'[^a-z0-9_]', '', image_name)

            # Check if exists
            if not force:
                existing = self.check_image_exists(images_folder, image_name)
                if existing:
                    results["skipped"] += 1
                    results["images"].append({
                        "name": prompt_info["name"],
                        "status": "skipped",
                        "file_path": existing
                    })
                    continue

            # Generate image
            print(f"    🎨 Generating: {prompt_info['name']}...")
            result = self.generate_image(
                prompt=prompt_info["prompt"],
                output_path=images_folder,
                image_name=image_name,
                width=width,
                height=height,
                platform=platform
            )

            result["name"] = prompt_info["name"]

            if result.get("success"):
                results["success"] += 1
                result["status"] = "generated"
            else:
                results["failed"] += 1
                result["status"] = "failed"

            results["images"].append(result)

        # Mark as done if all successful
        if results["success"] > 0 and results["failed"] == 0:
            images_marker.touch()
            print(f"    ✅ Images generated and marked as ready")

        return results

    def process_unprocessed_posts(
        self,
        platform: str = "xiaohongshu",
        force: bool = False
    ) -> Tuple[int, int, int]:
        """
        Process all posts that don't have images yet.

        Scans both temp_posts and selected_posts directories.

        Args:
            platform: Target platform
            force: Force regeneration

        Returns:
            Tuple of (processed, failed, skipped)
        """
        processed = 0
        failed = 0
        skipped = 0

        # Scan temp_posts
        if self.temp_posts_dir.exists():
            for folder in self.temp_posts_dir.iterdir():
                if not folder.is_dir():
                    continue

                # Only process folders that have post.ready (meaning post is generated)
                post_ready = folder / "post.ready"
                if not post_ready.exists():
                    continue

                # Check if images already generated
                images_ready = folder / self.images_ready_marker
                if images_ready.exists() and not force:
                    skipped += 1
                    continue

                print(f"\n  📁 Processing: {folder.name}")
                results = self.generate_images_for_post(folder, platform, force)

                if results.get("success", 0) > 0:
                    processed += 1
                elif results.get("failed", 0) > 0:
                    failed += 1
                else:
                    skipped += 1

        # Scan selected_posts
        if self.selected_posts_dir.exists():
            for post_file in self.selected_posts_dir.glob("post_*.md"):
                # Skip image-prompt files
                if post_file.name.startswith("image-prompt_"):
                    continue

                # Create a pseudo-folder for selected posts
                post_name = post_file.stem
                images_folder = self.post_images_dir / post_name
                images_marker = images_folder / self.images_ready_marker

                if images_marker.exists() and not force:
                    skipped += 1
                    continue

                print(f"\n  📄 Processing selected post: {post_name}")

                prompts = []

                # Priority 1: Look for companion image-prompt file
                image_prompt_file = self.selected_posts_dir / f"image-prompt_{post_name}.md"
                if image_prompt_file.exists():
                    try:
                        with open(image_prompt_file, 'r', encoding='utf-8') as f:
                            prompt_content = f.read()
                        prompts = self.extract_image_prompts_from_post(prompt_content, post_name)
                        if prompts:
                            print(f"    📄 Using prompts from: image-prompt_{post_name}.md")
                    except Exception as e:
                        print(f"    ⚠️  Failed to read image-prompt file: {e}")

                # Priority 2: Fall back to extracting from post file
                if not prompts:
                    try:
                        with open(post_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        prompts = self.extract_image_prompts_from_post(content, post_name)
                        if prompts:
                            print(f"    📄 Using prompts from: {post_file.name}")
                    except Exception as e:
                        print(f"    ❌ Failed to read: {e}")
                        failed += 1
                        continue

                if not prompts:
                    print(f"    ⚠️  No prompts extracted")
                    skipped += 1
                    continue

                # Generate
                width, height = get_platform_dimensions(platform)
                success_count = 0

                for prompt_info in prompts:
                    image_name = prompt_info["name"].lower().replace(" ", "_")
                    image_name = re.sub(r'[^a-z0-9_]', '', image_name)

                    print(f"    🎨 Generating: {prompt_info['name']}...")
                    result = self.generate_image(
                        prompt=prompt_info["prompt"],
                        output_path=images_folder,
                        image_name=image_name,
                        width=width,
                        height=height,
                        platform=platform
                    )

                    if result.get("success"):
                        success_count += 1
                        print(f"    ✅ Saved: {result['file_path']}")
                    else:
                        print(f"    ❌ Failed: {result.get('error', 'Unknown error')}")

                if success_count > 0:
                    images_marker.parent.mkdir(parents=True, exist_ok=True)
                    images_marker.touch()
                    processed += 1
                else:
                    failed += 1

        return processed, failed, skipped

    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a summary report of image generation."""
        report = f"""# Image Generation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- Processed: {results.get('processed', 0)}
- Failed: {results.get('failed', 0)}
- Skipped: {results.get('skipped', 0)}

## Details
"""

        for folder_result in results.get('folders', []):
            report += f"\n### {folder_result['folder']}\n"
            for img in folder_result.get('images', []):
                status = img.get('status', 'unknown')
                name = img.get('name', 'unnamed')
                if status == 'generated':
                    report += f"- ✅ {name}: {img.get('file_path', 'N/A')}\n"
                elif status == 'skipped':
                    report += f"- ⏭️ {name}: Already exists\n"
                else:
                    report += f"- ❌ {name}: {img.get('error', 'Failed')}\n"

        return report


if __name__ == "__main__":
    # Test the generator
    print("🧪 Testing Image Generator\n")

    generator = ImageGenerator()
    processed, failed, skipped = generator.process_unprocessed_posts(platform="xiaohongshu")

    print(f"\n📊 Summary:")
    print(f"   Processed: {processed}")
    print(f"   Failed: {failed}")
    print(f"   Skipped: {skipped}")
