"""Configuration management for Build-in-Public system.

Configuration Tiers:
    Tier 1: .env - Secrets, API keys, project paths (user-specific)
    Tier 2: This file (config.py) - Sensible defaults (override via .env)
    Tier 3: config/bip_settings.yaml - Advanced customization (optional)
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


def _convert_path_for_docker(path: str) -> str:
    """Convert Windows path to Docker container path if running in Docker.

    When running in Docker with PROJECTS_DIR mounted to /projects:
    - D:/git_repo/my-project -> /projects/my-project
    - /projects/my-project -> /projects/my-project (unchanged)
    """
    if not path:
        return path

    # Check if we're running in Docker (the /projects mount exists)
    if Path("/projects").exists():
        # If path already starts with /projects, use as-is
        if path.startswith("/projects"):
            return path

        # Convert Windows path (D:/git_repo/project) to Docker path (/projects/project)
        if re.match(r'^[A-Za-z]:[/\\]', path):
            # Extract project name (last component of the path)
            project_name = Path(path).name
            return f"/projects/{project_name}"

    return path


# =============================================================================
# TIER 2: Default Settings (can be overridden via .env)
# =============================================================================

class Settings(BaseSettings):
    """Application settings with sensible defaults.

    All settings here can be overridden by setting the corresponding
    environment variable in .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # -------------------------------------------------------------------------
    # Project Identity
    # -------------------------------------------------------------------------
    project_name: str = "build-in-public-social-post"
    environment: str = "development"

    # -------------------------------------------------------------------------
    # Monitored Projects (at least project_1 is required)
    # -------------------------------------------------------------------------
    project_1_name: str = "my-project"
    project_1_path: str = ""
    project_1_type: str = "productivity"

    project_2_name: Optional[str] = None
    project_2_path: Optional[str] = None
    project_2_type: Optional[str] = None

    project_3_name: Optional[str] = None
    project_3_path: Optional[str] = None
    project_3_type: Optional[str] = None

    project_4_name: Optional[str] = None
    project_4_path: Optional[str] = None
    project_4_type: Optional[str] = None

    # Private Projects (for calendar/meetings only, NOT for public posts)
    project_5_name: Optional[str] = None
    project_5_path: Optional[str] = None
    project_5_type: Optional[str] = None

    project_6_name: Optional[str] = None
    project_6_path: Optional[str] = None
    project_6_type: Optional[str] = None

    project_7_name: Optional[str] = None
    project_7_path: Optional[str] = None
    project_7_type: Optional[str] = None

    project_8_name: Optional[str] = None
    project_8_path: Optional[str] = None
    project_8_type: Optional[str] = None

    project_9_name: Optional[str] = None
    project_9_path: Optional[str] = None
    project_9_type: Optional[str] = None

    project_10_name: Optional[str] = None
    project_10_path: Optional[str] = None
    project_10_type: Optional[str] = None

    # -------------------------------------------------------------------------
    # AI Provider Settings
    # -------------------------------------------------------------------------
    ai_provider: str = "anthropic"  # anthropic, gemini, or openai
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Vertex AI (optional - preferred for Imagen 3 image generation)
    use_vertex_ai: bool = False
    vertex_project_id: Optional[str] = None
    vertex_location: str = "us-central1"

    # -------------------------------------------------------------------------
    # Post Generation Settings
    # -------------------------------------------------------------------------
    posts_per_day: int = 2
    min_word_count: int = 350
    max_word_count: int = 800
    lookback_days: int = 7
    max_tokens: int = 2048  # Max tokens for AI text generation

    # -------------------------------------------------------------------------
    # Social Media Credentials
    # -------------------------------------------------------------------------
    # Xiaohongshu (optional)
    xhs_username: Optional[str] = None
    xhs_password: Optional[str] = None
    xhs_cookie_file: str = "config/xhs_cookies.json"

    # X.com (Twitter)
    twitter_username: Optional[str] = None
    twitter_password: Optional[str] = None
    twitter_cookie_file: str = "config/twitter_cookies.json"

    # -------------------------------------------------------------------------
    # Scheduling Settings
    # -------------------------------------------------------------------------
    generation_time: str = "22:00"
    auto_post_enabled: bool = False
    timezone: str = "Asia/Shanghai"

    # Daily workflow timing
    daily_start_hour: int = 8   # When daily-auto starts (08:00)
    reschedule_hour: int = 23   # When to reschedule undone tasks (23:00)
    collect_hour: int = 20      # When to collect git data (20:00)
    select_hour: int = 20       # When to select posts (20:30 - adds 30min)

    # -------------------------------------------------------------------------
    # Calendar Settings
    # -------------------------------------------------------------------------
    # Gist upload (recommended for calendar subscription)
    calendar_upload_gist: bool = True
    github_gist_token: Optional[str] = None
    github_gist_id: Optional[str] = None

    # GitHub repo upload
    calendar_upload_github: bool = False

    # SFTP upload
    calendar_upload_sftp: bool = False
    sftp_remote_folder: str = "/usr/share/nginx/calendar"

    # Calendar work hours (for task scheduling)
    calendar_work_start_hour: int = 9
    calendar_lunch_start: int = 12
    calendar_lunch_end: int = 14
    calendar_gap_minutes: int = 20

    # -------------------------------------------------------------------------
    # Database & Logging
    # -------------------------------------------------------------------------
    database_url: str = "sqlite:///data/posts.db"
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    @property
    def base_dir(self) -> Path:
        """Get base directory."""
        return Path(__file__).parent.parent

    @property
    def projects(self) -> List[dict]:
        """Get list of monitored projects (public projects only, for post generation)."""
        projects = []

        # Add project 1 (required)
        if self.project_1_path:
            projects.append({
                "name": self.project_1_name,
                "path": _convert_path_for_docker(self.project_1_path),
                "type": self.project_1_type,
            })

        # Add optional projects 2-4 if configured
        optional_public = [
            (self.project_2_name, self.project_2_path, self.project_2_type),
            (self.project_3_name, self.project_3_path, self.project_3_type),
            (self.project_4_name, self.project_4_path, self.project_4_type),
        ]

        for name, path, proj_type in optional_public:
            if name and path and proj_type:
                projects.append({
                    "name": name,
                    "path": _convert_path_for_docker(path),
                    "type": proj_type,
                })

        return projects

    @property
    def all_projects(self) -> List[dict]:
        """Get list of ALL monitored projects (including private ones, for meetings/calendar)."""
        projects = self.projects.copy()

        # Add optional private projects if configured
        optional_projects = [
            (self.project_5_name, self.project_5_path, self.project_5_type),
            (self.project_6_name, self.project_6_path, self.project_6_type),
            (self.project_7_name, self.project_7_path, self.project_7_type),
            (self.project_8_name, self.project_8_path, self.project_8_type),
            (self.project_9_name, self.project_9_path, self.project_9_type),
            (self.project_10_name, self.project_10_path, self.project_10_type),
        ]

        for name, path, proj_type in optional_projects:
            if name and path and proj_type:
                projects.append({
                    "name": name,
                    "path": _convert_path_for_docker(path),
                    "type": proj_type,
                    "public": False,
                })

        return projects


# =============================================================================
# TIER 3: Advanced Settings (from config/bip_settings.yaml)
# =============================================================================

class BIPSettings:
    """Advanced customization settings loaded from YAML.

    These settings are for power users who want to customize:
    - AI model names
    - Posting schedules per platform
    - Image generation styles
    - Brand colors
    - Platform dimensions
    - Tech keywords for topic detection

    If the YAML file doesn't exist, sensible defaults are used.
    """

    # Default configuration (used when YAML file doesn't exist)
    DEFAULTS = {
        # AI Model Configuration
        "ai_models": {
            "text": {
                "anthropic": "claude-sonnet-4-5-20250929",
                "gemini": "gemini-2.5-flash",
                "openai": "gpt-4-turbo-preview",
            },
            "image": {
                "primary": "gemini-3-pro-image-preview",
                "fallback": "gemini-2.5-flash-preview-05-20",
                "openai": "dall-e-3",
            },
        },

        # Platform Posting Schedules (optimal times per platform)
        "posting_schedules": {
            "xiaohongshu": ["12:00", "18:30", "21:00"],
            "twitter": ["09:00", "12:00", "17:00"],
            "default": ["12:00", "18:00"],
        },

        # Scheduling Limits
        "scheduling": {
            "daily_quota": 2,       # Max posts per platform per day
            "max_days_ahead": 30,   # How far ahead to schedule
        },

        # Platform Image Dimensions
        "platform_dimensions": {
            "xiaohongshu": {"width": 1080, "height": 1440},  # 3:4
            "twitter": {"width": 1200, "height": 675},       # 16:9
            "instagram": {"width": 1080, "height": 1080},    # 1:1
            "default": {"width": 1200, "height": 675},
        },

        # Brand Colors (for image generation prompts)
        "brand_colors": {
            "primary": "#4A90D9",    # Tech blue
            "secondary": "#FF6B6B",  # Coral
            "accent": "#2ECC71",     # Green
        },

        # Post Type Visual Styles (for image generation)
        "post_type_styles": {
            "technical": "Clean, modern tech aesthetic with subtle gradients. Vector-style icons and diagrams. Professional color palette.",
            "story": "Warm, inviting illustration style. Hand-drawn elements with soft shadows. Narrative visual flow.",
            "tool_review": "Product photography style. Clean backgrounds with subtle depth. Professional lighting simulation.",
            "productivity": "Isometric 3D style. Organized workspace elements. Calm, focused color palette.",
            "announcement": "Bold, celebratory graphics. Dynamic composition with energy. Bright, optimistic colors.",
            "reflection": "Minimalist conceptual art. Thoughtful negative space. Muted, sophisticated palette.",
        },

        # Post Type Detection Keywords
        "post_type_keywords": {
            "technical": ["api", "code", "debug", "implement", "architecture", "database", "algorithm"],
            "story": ["journey", "learned", "realized", "story", "experience", "mistake", "growth"],
            "tool_review": ["tool", "review", "compared", "tried", "switched", "using", "recommend"],
            "productivity": ["productivity", "workflow", "routine", "habit", "system", "organize"],
            "announcement": ["launch", "release", "announce", "introducing", "new", "milestone", "achieved"],
            "reflection": ["reflect", "thinking", "wondering", "perspective", "insight", "observation"],
        },

        # Tech Keywords for Topic Detection
        "tech_keywords": [
            "API", "SaaS", "FIRE", "Docker", "FastAPI", "PostgreSQL", "Redis",
            "Kubernetes", "MongoDB", "React", "Vue", "Python", "TypeScript",
            "JavaScript", "Go", "Rust", "Java", "Node.js", "GraphQL", "REST",
            "AWS", "GCP", "Azure", "CI/CD", "DevOps", "Microservices",
        ],

        # Content Limits
        "content_limits": {
            "whisper_max_size_mb": 25,
            "url_content_max_chars": 10000,
            "http_timeout_seconds": 30,
            "audio_chunk_min_seconds": 60,
            "audio_chunk_max_seconds": 600,
        },
    }

    def __init__(self, config_path: str = "config/bip_settings.yaml"):
        """Initialize BIP settings.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._loaded = False

    def _load(self) -> None:
        """Load configuration from YAML file."""
        if self._loaded:
            return

        # Start with defaults
        self._config = self._deep_copy(self.DEFAULTS)

        # Override with YAML if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f) or {}
                self._deep_merge(self._config, yaml_config)
            except Exception as e:
                print(f"  ⚠️  Error loading {self.config_path}: {e}")
                print(f"      Using default settings.")

        self._loaded = True

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of nested dicts/lists."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj

    def _deep_merge(self, base: dict, override: dict) -> None:
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, *keys: str, default: Any = None) -> Any:
        """Get a nested configuration value.

        Args:
            *keys: Path to the configuration value (e.g., "ai_models", "text", "anthropic")
            default: Default value if not found

        Returns:
            The configuration value or default
        """
        self._load()

        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    # Convenience properties for common settings
    @property
    def ai_models(self) -> dict:
        """Get AI model configuration."""
        return self.get("ai_models", default=self.DEFAULTS["ai_models"])

    @property
    def posting_schedules(self) -> dict:
        """Get posting schedules per platform."""
        return self.get("posting_schedules", default=self.DEFAULTS["posting_schedules"])

    @property
    def scheduling(self) -> dict:
        """Get scheduling limits."""
        return self.get("scheduling", default=self.DEFAULTS["scheduling"])

    @property
    def platform_dimensions(self) -> dict:
        """Get platform image dimensions."""
        return self.get("platform_dimensions", default=self.DEFAULTS["platform_dimensions"])

    @property
    def brand_colors(self) -> dict:
        """Get brand colors."""
        return self.get("brand_colors", default=self.DEFAULTS["brand_colors"])

    @property
    def post_type_styles(self) -> dict:
        """Get post type visual styles."""
        return self.get("post_type_styles", default=self.DEFAULTS["post_type_styles"])

    @property
    def post_type_keywords(self) -> dict:
        """Get post type detection keywords."""
        return self.get("post_type_keywords", default=self.DEFAULTS["post_type_keywords"])

    @property
    def tech_keywords(self) -> list:
        """Get tech keywords for topic detection."""
        return self.get("tech_keywords", default=self.DEFAULTS["tech_keywords"])

    @property
    def content_limits(self) -> dict:
        """Get content limits."""
        return self.get("content_limits", default=self.DEFAULTS["content_limits"])

    def get_text_model(self, provider: str) -> str:
        """Get the text model name for a provider."""
        return self.get("ai_models", "text", provider,
                       default=self.DEFAULTS["ai_models"]["text"].get(provider, ""))

    def get_image_model(self, model_type: str = "primary") -> str:
        """Get the image model name."""
        return self.get("ai_models", "image", model_type,
                       default=self.DEFAULTS["ai_models"]["image"].get(model_type, ""))

    def get_platform_schedule(self, platform: str) -> list:
        """Get posting schedule for a platform."""
        schedules = self.posting_schedules
        return schedules.get(platform, schedules.get("default", ["12:00", "18:00"]))

    def get_platform_dimensions(self, platform: str) -> dict:
        """Get image dimensions for a platform."""
        dims = self.platform_dimensions
        return dims.get(platform, dims.get("default", {"width": 1200, "height": 675}))


# =============================================================================
# Global Instances
# =============================================================================

# Tier 2: Environment-based settings
settings = Settings()

# Tier 3: Advanced YAML-based settings
bip_settings = BIPSettings()

# Legacy compatibility (deprecated - use settings.projects instead)
class ProjectConfig:
    """Deprecated: Use settings.projects instead."""

    def __init__(self, config_path: str = "config/projects.yaml"):
        self.config_path = Path(config_path)
        self._config = None

    def load(self) -> dict:
        """Load configuration."""
        if not self.config_path.exists():
            # Return empty config instead of raising error
            return {"projects": [], "generation": {}}

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        return self._config

    @property
    def projects(self) -> List[dict]:
        """Get projects list."""
        if not self._config:
            self.load()
        return self._config.get('projects', []) if self._config else []

    @property
    def generation(self) -> dict:
        """Get generation config."""
        if not self._config:
            self.load()
        return self._config.get('generation', {}) if self._config else {}


project_config = ProjectConfig()
