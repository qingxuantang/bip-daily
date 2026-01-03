"""AI-powered post generator."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json
from jinja2 import Environment, FileSystemLoader

from src.models import PostData, GeneratedPost, PostStyle, PostLanguage
from src.config import settings, bip_settings


class PostGenerator:
    """Generate social media posts using AI and templates."""

    def __init__(self, ai_provider: str = None):
        """Initialize generator.

        Args:
            ai_provider: AI provider to use ('gemini', 'openai', or 'anthropic')
                        If None, will use fallback order: anthropic → gemini → openai
        """
        self.ai_provider = ai_provider or settings.ai_provider

        # Fallback order: Claude → Gemini → OpenAI
        self.provider_order = ["anthropic", "gemini", "openai"]

        # Store available providers
        self.available_providers = {}
        self.active_provider = None

        # Initialize Jinja2
        template_dir = Path(settings.base_dir) / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

        # Load writing style guide (kept for backward compatibility)
        style_file = Path(settings.base_dir) / "WRITING_STYLE_ANALYSIS.md"
        if style_file.exists():
            with open(style_file, 'r', encoding='utf-8') as f:
                self.style_guide = f.read()
        else:
            self.style_guide = ""

        # Path to style reference directory (all files loaded dynamically)
        self.style_reference_dir = Path(settings.base_dir) / "post-style-reference"

        # All style content (loaded dynamically from ALL .md files in directory)
        self.all_style_content = self._load_all_style_files()

        # Initialize all available AI clients
        self._init_all_ai_clients()

    def _init_all_ai_clients(self):
        """Initialize all available AI clients for fallback."""
        import os

        # Try to initialize Anthropic (Claude)
        if settings.anthropic_api_key:
            try:
                # Import and create custom httpx client without proxy
                import httpx
                from anthropic import Anthropic
                import anthropic

                # Create httpx client with explicit proxy=None
                http_client = httpx.Client(proxy=None)

                client = Anthropic(
                    api_key=settings.anthropic_api_key,
                    http_client=http_client
                )

                # Detect API version (old vs new)
                api_version = "old" if hasattr(client, 'completions') and not hasattr(client, 'messages') else "new"

                # Use appropriate model for API version
                if api_version == "new":
                    model = bip_settings.get_text_model("anthropic")
                else:
                    # Old API - use claude-2 or claude-instant-1
                    model = "claude-2"

                self.available_providers["anthropic"] = {
                    "client": client,
                    "model": model,
                    "api_version": api_version
                }
                print(f"  ✅ Anthropic (Claude) initialized (API: {api_version}, model: {model}, v{anthropic.__version__})")
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

                # Create httpx client with explicit proxy=None
                http_client = httpx.Client(proxy=None)

                self.available_providers["openai"] = {
                    "client": OpenAI(
                        api_key=settings.openai_api_key,
                        http_client=http_client
                    ),
                    "model": bip_settings.get_text_model("openai")
                }
                print("  ✅ OpenAI initialized")
            except Exception as e:
                print(f"  ⚠️  OpenAI initialization failed: {e}")

        if not self.available_providers:
            raise ValueError("No AI providers could be initialized. Check your API keys.")

    def _load_all_style_files(self) -> str:
        """Load ALL markdown files from post-style-reference directory.

        Automatically discovers and loads all .md files in the directory.
        Files are sorted alphabetically and combined with section headers.
        Excludes default_style_template.md (template only).

        Returns:
            Combined content of all style files, or empty string if none found
        """
        if not self.style_reference_dir.exists():
            print(f"  ⚠️  Style reference directory not found: {self.style_reference_dir}")
            return ""

        try:
            # Find all .md files (excluding template)
            style_files = [
                f for f in self.style_reference_dir.glob("*.md")
                if f.name != "default_style_template.md"
            ]

            if not style_files:
                print(f"  ⚠️  No style files found in {self.style_reference_dir}")
                print(f"      Add .md files to customize your writing style")
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
                        # Add file header and content
                        combined_content.append(f"# === {file_path.name} ===\n\n{content}")
                        total_chars += len(content)
                        print(f"  ✅ Loaded: {file_path.name} ({len(content)} chars)")

                except Exception as e:
                    print(f"  ⚠️  Error loading {file_path.name}: {e}")

            if not combined_content:
                print(f"  ⚠️  All style files were empty or failed to load")
                return ""

            result = "\n\n---\n\n".join(combined_content)
            print(f"  📚 Total style content: {len(style_files)} files, {total_chars} chars")
            return result

        except Exception as e:
            print(f"  ⚠️  Error loading style files: {e}")
            return ""

    def _load_all_style_references(self) -> Dict[str, str]:
        """Load all markdown files from the style reference directory.

        Returns:
            Dictionary of filename -> content
        """
        references = {}

        if not self.style_reference_dir.exists():
            print(f"  ⚠️  Style reference directory not found: {self.style_reference_dir}")
            return references

        try:
            for file_path in self.style_reference_dir.glob("*.md"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    references[file_path.stem] = content
                    print(f"  ✅ Loaded {file_path.name} ({len(content)} chars)")
                except Exception as e:
                    print(f"  ⚠️  Error loading {file_path.name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Error scanning style reference directory: {e}")

        return references

    def _create_generation_prompt(self, post_data: PostData, style: PostStyle, language: PostLanguage = PostLanguage.CHINESE) -> str:
        """Create prompt for AI generation.

        Args:
            post_data: Collected data
            style: Desired post style
            language: Target language (Chinese or English)

        Returns:
            Generation prompt
        """
        if language == PostLanguage.ENGLISH:
            return self._create_english_prompt(post_data, style)
        else:
            return self._create_chinese_prompt(post_data, style)

    def _create_chinese_prompt(self, post_data: PostData, style: PostStyle) -> str:
        """Create Chinese prompt for AI generation.

        Args:
            post_data: Collected data
            style: Desired post style

        Returns:
            Chinese generation prompt
        """
        # Prepare data summary
        data_summary = self._summarize_data(post_data)

        # Use dynamically loaded style content (all files from post-style-reference/)
        style_content = self.all_style_content if self.all_style_content else "No style guide loaded. Use neutral professional tone."

        prompt = f"""# 任务
根据以下数据生成一篇小红书 Build-in-Public 贴文。

# 写作风格指南（核心要求 - 必须严格遵守）

以下是从 post-style-reference 目录加载的所有风格指南文件：

{style_content}

# 贴文风格
{style.value} - {"日常进度更新" if style == PostStyle.CASUAL_UPDATE else
                "技术深度分享" if style == PostStyle.TECHNICAL_DEEP else
                "里程碑达成" if style == PostStyle.MILESTONE else
                "挑战与思考" if style == PostStyle.CHALLENGE else
                "周总结"}

# 数据来源

## Git 提交记录（过去7天）
{data_summary['git_summary']}

## Claude Code 对话要点
{data_summary['claude_summary']}

## 项目更新汇总
{data_summary['projects_summary']}

# 生成要求

1. **字数**：{settings.min_word_count}-{settings.max_word_count}字
2. **数据驱动**：基于实际收集的Git提交、Claude对话等具体数据生成内容，用真实的技术细节和进展说话，避免使用重复的套路化表述
3. **中英混用**：技术术语保留英文（如 FastAPI, SaaS, API）
4. **学习示例风格**：参考上面的"最近发布的贴文示例"，保持一致的语气、结构和表达方式
5. **项目提及**：基于实际收集到的数据，自然提及有更新的项目。如果某些配置的项目没有活动，可以简单提及"暂时搁置"
6. **聚焦实际进展**：内容应基于收集到的Git提交和Claude对话数据，而非预设的项目列表

# 输出格式

请直接输出贴文内容，无需额外说明。确保：
- 开头吸引人，直入主题
- **基于上述实际数据**：引用具体的Git提交信息、Claude对话主题、技术实现细节
- 用真实的技术进展和数据说话，而不是套路化的描述
- 真实的感受和思考
- 清晰的项目进展
- 合适的话题标签
- 风格与最近的贴文保持一致
- **✅ 提及有活动的项目**：基于收集到的数据自然提及项目

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
- 描述具体视觉元素（icons, devices, abstract shapes, workflow diagrams 等）
- 根据贴文内容设计视觉主题（如：AI assistant icons, productivity dashboard, code editor mockup 等）
- 指定风格（modern minimalist, tech aesthetic, professional 等）
- 提及配色（coral #FF6B6B, tech blue #4A90D9 为品牌色）
- 避免人脸和真人照片
- 适合小红书/社交媒体的视觉风格

现在请生成贴文（包含 Image Prompts 部分）：
"""
        return prompt

    def _create_english_prompt(self, post_data: PostData, style: PostStyle) -> str:
        """Create English prompt for AI generation.

        Args:
            post_data: Collected data
            style: Desired post style

        Returns:
            English generation prompt
        """
        # Prepare data summary
        data_summary = self._summarize_data(post_data)

        # Load viral post analysis dynamically
        viral_post_analysis = self._load_viral_post_analysis()

        # Determine style description
        style_desc = {
            PostStyle.CASUAL_UPDATE: "casual progress update",
            PostStyle.TECHNICAL_DEEP: "technical deep dive",
            PostStyle.MILESTONE: "milestone achievement",
            PostStyle.CHALLENGE: "challenge and reflection",
            PostStyle.WEEKLY_SUMMARY: "weekly summary"
        }.get(style, "casual update")

        # Use dynamically loaded style content (all files from post-style-reference/)
        style_content = self.all_style_content if self.all_style_content else "No style guide loaded. Use neutral professional tone."

        prompt = f"""# Task
Create an English post for X.com (Twitter) based on the following data.

# Writing Style Guidelines (MUST FOLLOW)

All style guide files loaded from post-style-reference directory:

{style_content}

# Post Style
{style_desc}

# Source Data

## Git Commits (Last 7 days)
{data_summary['git_summary']}

## Claude Code Discussion Topics
{data_summary['claude_summary']}

## Project Updates Summary
{data_summary['projects_summary']}

# Generation Requirements

1. **Length**: {settings.min_word_count}-{settings.max_word_count} words (count English words + characters)
2. **Data-Driven**: Base content on actual collected Git commits, Claude conversations, and specific technical details. Let real progress and data tell the story. Avoid repetitive clichés.
3. **Technical Terms**: Keep in English (FastAPI, SaaS, API, etc.)
4. **Project Mentions**: Mention projects naturally based on actual collected data. If some configured projects have no activity, you can briefly mention they're "on hold"
5. **Platform**: This is for X.com (Twitter), so make it engaging and shareable
6. **Focus on Real Progress**: Content should be based on collected Git commits and Claude conversation data, not on predefined project lists

# Output Format

Please output the post content directly, without additional explanations. Ensure:
- Engaging opening that hooks readers
- **Based on actual data above**: Reference specific Git commits, Claude conversation topics, technical implementation details
- Let real technical progress and data tell the story, not formulaic descriptions
- Real feelings and reflections
- Clear project progress
- Appropriate hashtags
- **✅ Mention projects with activity**: Based on collected data, mention relevant projects naturally

# Image Prompts Section (REQUIRED)

At the end of your post, add a `## Image Prompts` section for automatic image generation. Format:

```
## Image Prompts

### Cover
```
[Write an English image generation prompt describing visual elements, style, colors, etc.]
```
```

Image prompt requirements:
- Written in English (for Gemini Imagen 3 API)
- Describe specific visual elements (icons, devices, abstract shapes, workflow diagrams, etc.)
- Design visual theme based on post content (e.g., AI assistant icons, productivity dashboard, code editor mockup)
- Specify style (modern minimalist, tech aesthetic, professional, etc.)
- Include brand colors (coral #FF6B6B, tech blue #4A90D9)
- Avoid human faces and real person photos
- Suitable for X.com/Twitter visual style

Now please generate the English post (including Image Prompts section):
"""
        return prompt

    def _summarize_data(self, post_data: PostData) -> Dict[str, str]:
        """Summarize collected data for prompt.

        Args:
            post_data: Collected data

        Returns:
            Dictionary with summarized data
        """
        # Git summary
        git_lines = []
        for project_name, project_data in post_data.project_updates.items():
            commits = project_data.get('commits', [])
            if commits:
                git_lines.append(f"\n**{project_name}** ({len(commits)} commits):")
                for commit in commits[:5]:  # Top 5
                    git_lines.append(f"  - {commit.hash}: {commit.message}")

        git_summary = "\n".join(git_lines) if git_lines else "无提交记录"

        # Claude summary
        claude_lines = []
        for project_name, project_data in post_data.project_updates.items():
            conversations = project_data.get('conversations', [])
            topics = project_data.get('topics', [])
            if conversations or topics:
                claude_lines.append(f"\n**{project_name}**:")
                if topics:
                    claude_lines.append(f"  讨论话题: {', '.join(topics[:8])}")
                claude_lines.append(f"  活跃会话数: {len(conversations)}")

        claude_summary = "\n".join(claude_lines) if claude_lines else "无对话记录"

        # Projects summary - ALWAYS include ALL projects
        projects_lines = []
        active_projects = []
        inactive_projects = []

        for project_name, project_data in post_data.project_updates.items():
            desc = project_data.get('description', '')
            commits_count = project_data.get('commit_count', 0)
            conv_count = len(project_data.get('conversations', []))
            has_activity = project_data.get('has_activity', False)

            project_line = f"• **{project_name}**: {desc} ({commits_count} commits, {conv_count} sessions)"

            if has_activity:
                active_projects.append(project_line)
            else:
                inactive_projects.append(project_line)

        # Build comprehensive project summary
        all_projects_lines = []

        if active_projects:
            all_projects_lines.append("📊 有进展的项目：")
            all_projects_lines.extend(active_projects)

        if inactive_projects:
            all_projects_lines.append("\n⏸️ 本周暂无更新的项目：")
            all_projects_lines.extend(inactive_projects)

        projects_summary = "\n".join(all_projects_lines) if all_projects_lines else "无项目更新"

        return {
            "git_summary": git_summary,
            "claude_summary": claude_summary,
            "projects_summary": projects_summary,
        }

    def _call_ai(self, prompt: str) -> str:
        """Call AI API to generate content with fallback support.

        Args:
            prompt: Generation prompt

        Returns:
            Generated content

        Raises:
            Exception: If all providers fail
        """
        last_error = None

        # Try providers in order: anthropic → gemini → openai
        for provider in self.provider_order:
            if provider not in self.available_providers:
                continue

            try:
                print(f"    🔄 Trying {provider}...")
                provider_info = self.available_providers[provider]
                client = provider_info["client"]
                model = provider_info["model"]

                if provider == "anthropic":
                    api_version = provider_info.get("api_version", "new")

                    if api_version == "new":
                        # New Messages API (anthropic >= 0.18.0)
                        response = client.messages.create(
                            model=model,
                            max_tokens=2048,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        content = response.content[0].text
                    else:
                        # Old Completions API (anthropic < 0.18.0)
                        from anthropic import HUMAN_PROMPT, AI_PROMPT
                        formatted_prompt = f"{HUMAN_PROMPT} {prompt}{AI_PROMPT}"
                        response = client.completions.create(
                            model=model,
                            max_tokens_to_sample=2048,
                            prompt=formatted_prompt
                        )
                        content = response.completion

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

                # If we got here, the call succeeded
                self.active_provider = provider
                print(f"    ✅ Success with {provider}")
                return content

            except Exception as e:
                last_error = e
                print(f"    ❌ {provider} failed: {str(e)[:100]}")
                continue

        # If we got here, all providers failed
        raise Exception(f"All AI providers failed. Last error: {last_error}")

    def generate_post(self, post_data: PostData, style: PostStyle, language: PostLanguage = PostLanguage.CHINESE) -> GeneratedPost:
        """Generate a single post.

        Args:
            post_data: Collected data
            style: Post style
            language: Target language (Chinese or English)

        Returns:
            GeneratedPost object
        """
        lang_name = "Chinese" if language == PostLanguage.CHINESE else "English"
        print(f"  🤖 Generating {lang_name} {style.value} post with fallback support...")

        # Create prompt
        prompt = self._create_generation_prompt(post_data, style, language)

        # Call AI
        content = self._call_ai(prompt)

        # Extract hashtags
        hashtags = self._extract_hashtags(content)

        # Count words (Chinese characters + English words)
        word_count = self._count_words(content)

        # Extract mentioned projects
        projects_mentioned = [
            p for p in post_data.project_updates.keys()
            if p in content or p.replace('-', ' ') in content
        ]

        # Extract technical keywords
        all_topics = set()
        for project_data in post_data.project_updates.values():
            all_topics.update(project_data.get('topics', []))

        technical_keywords = [
            topic for topic in all_topics
            if topic.lower() in content.lower()
        ]

        return GeneratedPost(
            content=content,
            style=style,
            language=language,
            hashtags=hashtags,
            word_count=word_count,
            projects_mentioned=projects_mentioned,
            technical_keywords=technical_keywords,
            metadata={
                "ai_provider": self.active_provider,
                "model": self.available_providers[self.active_provider]["model"],
                "generated_at": datetime.now().isoformat(),
            }
        )

    def generate_multiple_posts(
        self,
        post_data: PostData,
        count: int = 2
    ) -> List[GeneratedPost]:
        """Generate multiple posts with different styles in both Chinese and English.

        Args:
            post_data: Collected data
            count: Number of posts PER LANGUAGE to generate (will generate count*2 total)

        Returns:
            List of GeneratedPost objects (Chinese posts first, then English posts)
        """
        posts = []

        # Select styles based on data
        styles = self._select_styles(post_data, count)

        # Generate Chinese posts
        print(f"\n🇨🇳 Generating {count} Chinese posts...")
        for i, style in enumerate(styles, 1):
            print(f"\n📝 Generating Chinese post {i}/{count}...")
            post = self.generate_post(post_data, style, PostLanguage.CHINESE)
            posts.append(post)
            print(f"   ✅ Generated {post.word_count} words")

        # Generate English posts
        print(f"\n🇬🇧 Generating {count} English posts...")
        for i, style in enumerate(styles, 1):
            print(f"\n📝 Generating English post {i}/{count}...")
            post = self.generate_post(post_data, style, PostLanguage.ENGLISH)
            posts.append(post)
            print(f"   ✅ Generated {post.word_count} words")

        return posts

    def _select_styles(self, post_data: PostData, count: int) -> List[PostStyle]:
        """Select appropriate styles based on data.

        Args:
            post_data: Collected data
            count: Number of styles needed

        Returns:
            List of PostStyle enums
        """
        styles = []

        # Determine based on activity level
        total_commits = len(post_data.git_commits)

        if total_commits >= 10:
            # High activity - use milestone or weekly summary
            styles.append(PostStyle.MILESTONE)
            if count > 1:
                styles.append(PostStyle.WEEKLY_SUMMARY)
        elif total_commits >= 5:
            # Medium activity - use casual update and technical deep
            styles.append(PostStyle.CASUAL_UPDATE)
            if count > 1:
                styles.append(PostStyle.TECHNICAL_DEEP)
        else:
            # Low activity - use challenge or casual
            styles.append(PostStyle.CHALLENGE)
            if count > 1:
                styles.append(PostStyle.CASUAL_UPDATE)

        # Ensure we have enough styles
        all_styles = list(PostStyle)
        while len(styles) < count:
            for style in all_styles:
                if style not in styles:
                    styles.append(style)
                    break

        return styles[:count]

    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content.

        Args:
            content: Post content

        Returns:
            List of hashtags (without #)
        """
        import re
        hashtags = re.findall(r'#(\S+)', content)
        return hashtags

    def _count_words(self, content: str) -> int:
        """Count words in content (Chinese chars + English words).

        Args:
            content: Post content

        Returns:
            Word count
        """
        import re

        # Remove hashtags for counting
        content = re.sub(r'#\S+', '', content)

        # Count Chinese characters
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))

        # Count English words
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', content))

        return chinese_chars + english_words


if __name__ == "__main__":
    from src.collectors.aggregator import DataAggregator

    # Test generation
    print("🧪 Testing Post Generator\n")

    # Collect data
    aggregator = DataAggregator(lookback_days=7)
    data = aggregator.collect_all_data()

    # Generate posts
    generator = PostGenerator()
    posts = generator.generate_multiple_posts(data, count=2)

    print("\n" + "=" * 60)
    print("✨ GENERATED POSTS")
    print("=" * 60)

    for i, post in enumerate(posts, 1):
        print(f"\n📄 Post {i} ({post.style.value})")
        print(f"   Words: {post.word_count}")
        print(f"   Hashtags: {', '.join(post.hashtags)}")
        print(f"   Projects: {', '.join(post.projects_mentioned)}")
        print("\n" + "-" * 60)
        print(post.content)
        print("-" * 60)
