"""Temp post generator - processes new folders in data/temp_posts."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json

from src.config import settings, bip_settings


class TempPostGenerator:
    """Generate posts from temp_posts folder content."""

    # Supported audio file extensions for transcription
    AUDIO_EXTENSIONS = {'.mp4', '.m4a', '.mp3', '.wav', '.webm', '.ogg', '.flac', '.mpeg', '.mpga'}

    # URL regex pattern - matches http/https URLs
    URL_PATTERN = re.compile(
        r'https?://[^\s<>\[\]()"\'\`\u4e00-\u9fff]+',
        re.IGNORECASE
    )

    # URLs to skip (common non-content URLs)
    SKIP_URL_PATTERNS = [
        r'xiaohongshu\.com/user/profile',  # XHS profile
        r'github\.com/.*/(?:blob|tree|commit)',  # GitHub code views
        r'\.(jpg|jpeg|png|gif|svg|webp|ico|pdf|mp4|mp3|wav)$',  # Media files
    ]

    def __init__(self):
        """Initialize the temp post generator."""
        self.temp_posts_dir = Path(settings.base_dir) / "data" / "temp_posts"
        self.style_reference_dir = Path(settings.base_dir) / "post-style-reference"
        self.ready_marker = "post.ready"
        self.output_file = "post.md"
        self.output_file_link_failed = "post_链接内容无法获取.md"  # Output filename when URL fetch fails

        # Track URL fetch failures per folder
        self.url_fetch_failed = False

        # Initialize AI providers (same as PostGenerator)
        self.available_providers = {}
        self.active_provider = None
        self.openai_client = None  # Separate reference for Whisper API
        self._init_ai_clients()

        # Load all style files dynamically
        self.all_style_content = self._load_all_style_files()

    def _load_all_style_files(self) -> str:
        """Load ALL markdown files from post-style-reference directory.

        Automatically discovers and loads all .md files in the directory.
        Files are sorted alphabetically and combined with section headers.
        Excludes default_style_template.md (template only).

        Returns:
            Combined content of all style files, or empty string if none found
        """
        if not self.style_reference_dir.exists():
            return ""

        try:
            # Find all .md files (excluding template)
            style_files = [
                f for f in self.style_reference_dir.glob("*.md")
                if f.name != "default_style_template.md"
            ]

            if not style_files:
                return ""

            # Sort files alphabetically
            style_files = sorted(style_files)

            # Load and combine all files
            combined_content = []
            total_chars = 0

            for file_path in style_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if content.strip():
                        combined_content.append(f"# === {file_path.name} ===\n\n{content}")
                        total_chars += len(content)
                        print(f"  ✅ Loaded: {file_path.name} ({len(content)} chars)")

                except Exception as e:
                    print(f"  ⚠️  Error loading {file_path.name}: {e}")

            if not combined_content:
                return ""

            result = "\n\n---\n\n".join(combined_content)
            print(f"  📚 Total style content: {len(style_files)} files, {total_chars} chars")
            return result

        except Exception as e:
            print(f"  ⚠️  Error loading style files: {e}")
            return ""

    def _init_ai_clients(self):
        """Initialize AI clients for generation."""
        # Try to initialize Anthropic (Claude)
        if settings.anthropic_api_key:
            try:
                import httpx
                from anthropic import Anthropic

                http_client = httpx.Client(proxy=None)
                client = Anthropic(
                    api_key=settings.anthropic_api_key,
                    http_client=http_client
                )
                self.available_providers["anthropic"] = {
                    "client": client,
                    "model": bip_settings.get_text_model("anthropic")
                }
                print("  ✅ Anthropic (Claude) initialized")
            except Exception as e:
                print(f"  ⚠️  Anthropic initialization failed: {e}")

        # Try to initialize Gemini
        if settings.gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=settings.gemini_api_key)
                self.available_providers["gemini"] = {
                    "client": client,
                    "model": bip_settings.get_text_model("gemini")
                }
                print("  ✅ Gemini initialized")
            except Exception as e:
                print(f"  ⚠️  Gemini initialization failed: {e}")

        # Try to initialize OpenAI
        if settings.openai_api_key:
            try:
                import httpx
                from openai import OpenAI

                http_client = httpx.Client(proxy=None)
                openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    http_client=http_client
                )
                self.available_providers["openai"] = {
                    "client": openai_client,
                    "model": bip_settings.get_text_model("openai")
                }
                # Store reference for Whisper API usage
                self.openai_client = openai_client
                print("  ✅ OpenAI initialized (includes Whisper for audio transcription)")
            except Exception as e:
                print(f"  ⚠️  OpenAI initialization failed: {e}")

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped (non-content URLs).

        Args:
            url: URL to check

        Returns:
            True if URL should be skipped
        """
        for pattern in self.SKIP_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def extract_urls_from_text(self, text: str) -> List[str]:
        """Extract URLs from text content.

        Args:
            text: Text content to search for URLs

        Returns:
            List of unique URLs found
        """
        urls = self.URL_PATTERN.findall(text)
        # Clean and deduplicate
        unique_urls = []
        seen = set()
        for url in urls:
            # Clean trailing punctuation
            url = url.rstrip('.,;:!?')
            if url not in seen and not self._should_skip_url(url):
                seen.add(url)
                unique_urls.append(url)
        return unique_urls

    def fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch content from a URL and convert to readable text.

        Args:
            url: URL to fetch

        Returns:
            Extracted text content or None if failed
        """
        try:
            import httpx

            print(f"    🔗 Fetching: {url[:60]}...")

            # Configure httpx client with reasonable timeout
            with httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
            ) as client:
                response = client.get(url)
                response.raise_for_status()

                content_type = response.headers.get('content-type', '').lower()

                # Only process HTML content
                if 'text/html' not in content_type and 'text/plain' not in content_type:
                    print(f"    ⚠️  Skipping non-HTML content: {content_type}")
                    return None

                html_content = response.text

                # Try to use html2text for conversion
                try:
                    import html2text
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.ignore_images = True
                    h.ignore_emphasis = False
                    h.body_width = 0  # Don't wrap lines
                    text = h.handle(html_content)
                except ImportError:
                    # Fallback: basic HTML tag removal
                    text = self._basic_html_to_text(html_content)

                # Clean up the text
                text = self._clean_extracted_text(text)

                if len(text) > 100:  # Only return if we got meaningful content
                    print(f"    ✅ Fetched {len(text)} chars from URL")
                    return text
                else:
                    print(f"    ⚠️  URL returned very little content ({len(text)} chars)")
                    return None

        except Exception as e:
            print(f"    ❌ Failed to fetch URL: {str(e)[:100]}")
            return None

    def _basic_html_to_text(self, html: str) -> str:
        """Basic HTML to text conversion without external libraries.

        Args:
            html: HTML content

        Returns:
            Plain text
        """
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # Convert common block elements to newlines
        html = re.sub(r'</(p|div|h[1-6]|li|tr|br)[^>]*>', '\n', html, flags=re.IGNORECASE)
        # Remove all remaining tags
        html = re.sub(r'<[^>]+>', '', html)
        # Decode common HTML entities
        html = html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        html = html.replace('&quot;', '"').replace('&#39;', "'")
        return html

    def _clean_extracted_text(self, text: str) -> str:
        """Clean up extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        # Remove lines that are just whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        text = '\n'.join(lines)
        # Truncate if too long (keep first 10000 chars for AI processing)
        if len(text) > 10000:
            text = text[:10000] + "\n\n[... 内容已截断 ...]"
        return text

    def find_unprocessed_folders(self) -> List[Path]:
        """Find folders that don't have a post.ready marker.

        Returns:
            List of folder paths that need processing
        """
        unprocessed = []

        if not self.temp_posts_dir.exists():
            print(f"  ⚠️  Temp posts directory not found: {self.temp_posts_dir}")
            return unprocessed

        for item in self.temp_posts_dir.iterdir():
            if item.is_dir():
                ready_file = item / self.ready_marker
                if not ready_file.exists():
                    unprocessed.append(item)

        return unprocessed

    # Whisper API file size limit (25MB)
    WHISPER_MAX_SIZE = 25 * 1024 * 1024  # 25MB in bytes

    def transcribe_audio_file(self, audio_path: Path) -> Optional[str]:
        """Transcribe an audio file using OpenAI Whisper API.

        Handles large files by splitting them into chunks.

        Args:
            audio_path: Path to the audio file

        Returns:
            Transcribed text or None if failed
        """
        if not self.openai_client:
            print(f"    ⚠️  OpenAI client not available for transcription")
            return None

        try:
            print(f"    🎙️  Transcribing: {audio_path.name}")

            # Check file size
            file_size = audio_path.stat().st_size
            if file_size > self.WHISPER_MAX_SIZE:
                print(f"    📦 Large file detected ({file_size / (1024*1024):.1f}MB > 25MB limit)")
                return self._transcribe_large_audio(audio_path)

            # Small file - direct transcription
            with open(audio_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )

            print(f"    ✅ Transcription complete ({len(transcript)} chars)")
            return transcript

        except Exception as e:
            print(f"    ❌ Transcription failed for {audio_path.name}: {e}")
            return None

    def _transcribe_large_audio(self, audio_path: Path) -> Optional[str]:
        """Transcribe a large audio file by splitting it into chunks.

        Args:
            audio_path: Path to the audio file

        Returns:
            Combined transcript or None if failed
        """
        import subprocess
        import tempfile

        try:
            # Get audio duration using ffprobe
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
                capture_output=True, text=True
            )
            total_duration = float(result.stdout.strip())
            print(f"    ⏱️  Audio duration: {total_duration:.0f}s")

            # Calculate chunk size (aim for ~20MB chunks to be safe)
            # Estimate based on file size and duration
            file_size = audio_path.stat().st_size
            bytes_per_second = file_size / total_duration
            chunk_duration = int(20 * 1024 * 1024 / bytes_per_second)  # ~20MB in seconds
            chunk_duration = max(60, min(chunk_duration, 600))  # Between 1-10 minutes

            # Calculate number of chunks
            num_chunks = int(total_duration / chunk_duration) + 1
            print(f"    🔪 Splitting into {num_chunks} chunk(s) ({chunk_duration}s each)")

            transcripts = []

            with tempfile.TemporaryDirectory() as temp_dir:
                for i in range(num_chunks):
                    start_time = i * chunk_duration
                    if start_time >= total_duration:
                        break

                    # Extract chunk using ffmpeg
                    chunk_path = Path(temp_dir) / f"chunk_{i}.mp3"
                    subprocess.run(
                        ['ffmpeg', '-y', '-i', str(audio_path),
                         '-ss', str(start_time), '-t', str(chunk_duration),
                         '-acodec', 'libmp3lame', '-ab', '128k',
                         str(chunk_path)],
                        capture_output=True, check=True
                    )

                    # Transcribe chunk
                    print(f"    🔄 Transcribing chunk {i+1}/{num_chunks}...")
                    with open(chunk_path, 'rb') as chunk_file:
                        chunk_transcript = self.openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=chunk_file,
                            response_format="text"
                        )
                    transcripts.append(chunk_transcript)

            # Combine transcripts
            combined = " ".join(transcripts)
            print(f"    ✅ Large file transcription complete ({len(combined)} chars)")
            return combined

        except Exception as e:
            print(f"    ❌ Large file transcription failed: {e}")
            return None

    def find_audio_files(self, folder: Path) -> List[Path]:
        """Find all audio files in a folder.

        Args:
            folder: Path to the folder

        Returns:
            List of audio file paths
        """
        audio_files = []

        for file_path in folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.AUDIO_EXTENSIONS:
                audio_files.append(file_path)

        return audio_files

    def read_folder_content(self, folder: Path) -> Dict[str, str]:
        """Read all markdown content, audio transcripts, and URL content from a folder.

        Args:
            folder: Path to the folder

        Returns:
            Dictionary with filename -> content (includes audio transcripts and URL content)
        """
        content = {}
        # Reset URL fetch failure flag for this folder
        self.url_fetch_failed = False
        all_urls = []

        # Read markdown files
        for file_path in folder.glob("*.md"):
            # Skip the output file if it exists
            if file_path.name == self.output_file or file_path.name == self.output_file_link_failed:
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    content[file_path.name] = file_content
                print(f"    📄 Read: {file_path.name} ({len(file_content)} chars)")

                # Extract URLs from this file
                urls = self.extract_urls_from_text(file_content)
                all_urls.extend(urls)

            except Exception as e:
                print(f"    ⚠️  Failed to read {file_path.name}: {e}")

        # Process audio files
        audio_files = self.find_audio_files(folder)
        if audio_files:
            print(f"    🎵 Found {len(audio_files)} audio file(s)")

            for audio_path in audio_files:
                transcript = self.transcribe_audio_file(audio_path)
                if transcript:
                    # Store transcript with a descriptive key
                    transcript_key = f"[Audio Transcript] {audio_path.name}"
                    content[transcript_key] = transcript

                    # Save transcript to a file for future reference
                    self._save_transcript(folder, audio_path.name, transcript)

        # Process URLs found in markdown files
        if all_urls:
            # Deduplicate URLs
            unique_urls = list(dict.fromkeys(all_urls))
            print(f"    🌐 Found {len(unique_urls)} URL(s) to fetch")

            for url in unique_urls:
                url_content = self.fetch_url_content(url)
                if url_content:
                    # Store URL content with a descriptive key
                    url_key = f"[URL Content] {url[:50]}..."
                    content[url_key] = url_content

                    # Save URL content to a file for future reference
                    self._save_url_content(folder, url, url_content)
                else:
                    # Mark that URL fetch failed
                    self.url_fetch_failed = True
                    print(f"    ⚠️  URL fetch failed, will note in output filename")

        return content

    def _save_url_content(self, folder: Path, url: str, url_content: str):
        """Save fetched URL content to a markdown file.

        Args:
            folder: Path to the folder
            url: Original URL
            url_content: Fetched and cleaned content
        """
        # Create a safe filename from URL
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        url_filename = f"url_content_{url_hash}.md"
        url_path = folder / url_filename

        try:
            with open(url_path, 'w', encoding='utf-8') as f:
                f.write(f"# URL Content: {url}\n\n")
                f.write(f"**Fetched at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(url_content)

            print(f"    💾 Saved URL content: {url_filename}")
        except Exception as e:
            print(f"    ⚠️  Failed to save URL content: {e}")

    def _save_transcript(self, folder: Path, audio_filename: str, transcript: str):
        """Save audio transcript to a markdown file.

        Args:
            folder: Path to the folder
            audio_filename: Original audio file name
            transcript: Transcribed text
        """
        # Create transcript filename based on audio filename
        transcript_filename = f"transcript_{audio_filename.rsplit('.', 1)[0]}.md"
        transcript_path = folder / transcript_filename

        try:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# Audio Transcript: {audio_filename}\n\n")
                f.write(f"**Transcribed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Model:** OpenAI Whisper-1\n\n")
                f.write("---\n\n")
                f.write(transcript)

            print(f"    💾 Saved transcript: {transcript_filename}")
        except Exception as e:
            print(f"    ⚠️  Failed to save transcript: {e}")

    def load_style_references(self) -> str:
        """Load all style reference content.

        Returns:
            Combined style reference content
        """
        references = []

        if not self.style_reference_dir.exists():
            return ""

        for file_path in self.style_reference_dir.glob("*.md"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                references.append(f"## {file_path.stem}\n\n{content}")
                print(f"  ✅ Loaded style reference: {file_path.name}")
            except Exception as e:
                print(f"  ⚠️  Failed to load {file_path.name}: {e}")

        return "\n\n---\n\n".join(references)

    def create_prompt(self, folder_name: str, source_content: Dict[str, str], style_references: str) -> str:
        """Create the generation prompt.

        Args:
            folder_name: Name of the source folder (topic)
            source_content: Dictionary of source file contents
            style_references: Combined style reference content

        Returns:
            Generation prompt
        """
        # Combine source content
        source_text = ""
        for filename, content in source_content.items():
            source_text += f"\n### 来源文件: {filename}\n\n{content}\n"

        # Use dynamically loaded style content (all files from post-style-reference/)
        style_content = self.all_style_content if self.all_style_content else "No style guide loaded. Use neutral professional tone."

        prompt = f"""# 任务

根据以下来源材料，生成一篇小红书 Build-in-Public 风格的贴文。

# 主题

{folder_name}

# 来源材料
{source_text}

# 写作风格指南（核心要求 - 必须严格遵守）

{style_content}

# 补充风格参考

{style_references}

# 写作要求

1. **字数**: 350-800字
2. **🔗 来源链接**: 如果来源材料中包含URL链接，在贴文末尾附上该链接

# 输出格式

请直接输出贴文内容，无需额外说明。确保：
- 开头吸引人，直入主题
- 基于来源材料提取核心洞察
- 用真实的观点和数据说话
- 包含合适的话题标签
- 🔗 如有来源链接，附在末尾

# 图片生成提示（必须包含）

在贴文末尾，添加一个 `## Image Prompts` 部分，用于自动生成配图。格式如下：

```
## Image Prompts

### Cover
```
[在这里写封面图的英文生成提示，描述图片视觉元素、风格、配色等]
```
```

图片提示要求：
- 使用英文撰写（Gemini Imagen 3 API 需要英文）
- 描述具体视觉元素（icons, devices, abstract shapes 等）
- 指定风格（modern minimalist, tech aesthetic, professional 等）
- 提及配色（coral #FF6B6B, tech blue #4A90D9 为品牌色）
- 避免人脸和真人照片
- 适合小红书/社交媒体的视觉风格

现在请生成贴文（包含 Image Prompts 部分）：
"""
        return prompt

    def _call_ai(self, prompt: str) -> str:
        """Call AI API to generate content.

        Args:
            prompt: Generation prompt

        Returns:
            Generated content
        """
        provider_order = ["anthropic", "gemini", "openai"]
        last_error = None

        for provider in provider_order:
            if provider not in self.available_providers:
                continue

            try:
                print(f"    🔄 Trying {provider}...")
                provider_info = self.available_providers[provider]
                client = provider_info["client"]
                model = provider_info["model"]

                if provider == "anthropic":
                    response = client.messages.create(
                        model=model,
                        max_tokens=2048,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    content = response.content[0].text

                elif provider == "openai":
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=2048,
                    )
                    content = response.choices[0].message.content

                elif provider == "gemini":
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    content = response.text

                self.active_provider = provider
                print(f"    ✅ Success with {provider}")
                return content

            except Exception as e:
                last_error = e
                print(f"    ❌ {provider} failed: {str(e)[:100]}")
                continue

        raise Exception(f"All AI providers failed. Last error: {last_error}")

    def generate_post(self, folder: Path) -> Optional[str]:
        """Generate a post from folder content.

        Args:
            folder: Path to the folder

        Returns:
            Generated post content or None if failed
        """
        folder_name = folder.name
        print(f"\n  📁 Processing: {folder_name}")

        # Read source content (markdown files and audio transcripts)
        source_content = self.read_folder_content(folder)
        if not source_content:
            print(f"    ⚠️  No source content found in {folder_name} (no markdown files or audio files)")
            return None

        # Load style references
        print(f"\n  📚 Loading style references...")
        style_references = self.load_style_references()

        # Create prompt
        prompt = self.create_prompt(folder_name, source_content, style_references)

        # Generate post
        print(f"\n  🤖 Generating post...")
        try:
            post_content = self._call_ai(prompt)
            return post_content
        except Exception as e:
            print(f"    ❌ Generation failed: {e}")
            return None

    def _extract_image_prompts(self, content: str) -> tuple:
        """Extract Image Prompts section from content.

        Args:
            content: Full post content

        Returns:
            Tuple of (post_content_without_prompts, image_prompts_section)
        """
        import re

        # Look for ## Image Prompts or ## 图片生成提示 section
        patterns = [
            r'\n## Image Prompts\s*\n',
            r'\n## 图片生成提示\s*\n',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                split_pos = match.start()
                post_content = content[:split_pos].rstrip()
                image_prompts = content[split_pos:].strip()
                return post_content, image_prompts

        # No image prompts section found
        return content, None

    def save_post(self, folder: Path, content: str) -> Path:
        """Save generated post to folder.

        Extracts Image Prompts section and saves to separate file.
        Uses different filename if URL fetch failed.

        Args:
            folder: Path to the folder
            content: Post content (may include Image Prompts section)

        Returns:
            Path to saved post file
        """
        # Extract image prompts from content
        post_content, image_prompts = self._extract_image_prompts(content)

        # Choose filename based on URL fetch status
        if self.url_fetch_failed:
            output_filename = self.output_file_link_failed
            url_note = "\n**⚠️ Note:** 部分链接内容无法获取，贴文基于已有材料生成\n"
        else:
            output_filename = self.output_file
            url_note = ""

        output_path = folder / output_filename

        # Add metadata header to post
        full_content = f"""# Generated Post - {folder.name}

**Generated at:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**AI Provider:** {self.active_provider}{url_note}

---

{post_content}
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        if self.url_fetch_failed:
            print(f"    💾 Post saved to: {output_path} (链接内容无法获取)")
        else:
            print(f"    💾 Post saved to: {output_path}")

        # Save image prompts to separate file if extracted
        if image_prompts:
            image_prompt_path = folder / "image-prompt.md"
            image_prompt_content = f"""# Image Generation Prompts - {folder.name}

**Generated at:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**For use with:** Gemini Imagen 3 API

---

{image_prompts}
"""
            with open(image_prompt_path, 'w', encoding='utf-8') as f:
                f.write(image_prompt_content)
            print(f"    🎨 Image prompts saved to: {image_prompt_path}")
        else:
            print(f"    ⚠️  No image prompts found in generated content")

        return output_path

    def mark_as_processed(self, folder: Path):
        """Create post.ready marker in folder.

        Args:
            folder: Path to the folder
        """
        ready_path = folder / self.ready_marker
        ready_path.touch()
        print(f"    ✅ Marked as processed: {ready_path}")

    def process_folder(self, folder: Path) -> bool:
        """Process a single folder: generate post and mark as done.

        Args:
            folder: Path to the folder

        Returns:
            True if successful
        """
        try:
            # Generate post
            content = self.generate_post(folder)
            if not content:
                return False

            # Save post
            self.save_post(folder, content)

            # Mark as processed
            self.mark_as_processed(folder)

            return True

        except Exception as e:
            print(f"    ❌ Failed to process {folder.name}: {e}")
            return False

    def process_all_unprocessed(self) -> Tuple[int, int]:
        """Process all unprocessed folders.

        Returns:
            Tuple of (processed_count, failed_count)
        """
        print("\n🔍 Scanning for unprocessed folders...")

        unprocessed = self.find_unprocessed_folders()

        if not unprocessed:
            print("  ✅ No unprocessed folders found")
            return 0, 0

        print(f"  📂 Found {len(unprocessed)} unprocessed folder(s)")

        processed = 0
        failed = 0

        for folder in unprocessed:
            if self.process_folder(folder):
                processed += 1
            else:
                failed += 1

        return processed, failed


if __name__ == "__main__":
    # Test the generator
    print("🧪 Testing Temp Post Generator\n")

    generator = TempPostGenerator()
    processed, failed = generator.process_all_unprocessed()

    print(f"\n📊 Summary:")
    print(f"   Processed: {processed}")
    print(f"   Failed: {failed}")
