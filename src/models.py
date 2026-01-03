"""Data models for the Build-in-Public system."""

# Fix for pyenv Python 3.12 without built-in sqlite3 support
import sys
try:
    import sqlite3
except ModuleNotFoundError:
    # Use pysqlite3-binary as a replacement
    import pysqlite3 as sqlite3
    sys.modules['sqlite3'] = sqlite3

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config import settings


Base = declarative_base()


class PostStatus(str, Enum):
    """Post status enumeration."""
    DRAFT = "draft"
    SELECTED = "selected"
    SCHEDULED = "scheduled"  # Post is scheduled for future publishing
    PUBLISHED = "published"
    REJECTED = "rejected"


class PostStyle(str, Enum):
    """Post style enumeration."""
    CASUAL_UPDATE = "casual_update"
    TECHNICAL_DEEP = "technical_deep"
    MILESTONE = "milestone"
    CHALLENGE = "challenge"
    WEEKLY_SUMMARY = "weekly_summary"


class PostLanguage(str, Enum):
    """Post language enumeration."""
    CHINESE = "zh"
    ENGLISH = "en"


# Pydantic Models for validation
class GitCommit(BaseModel):
    """Git commit information."""
    hash: str
    message: str
    author: str
    timestamp: datetime
    project: str


class ClaudeConversation(BaseModel):
    """Claude Code conversation extract."""
    session_id: str
    project: str
    messages: List[dict]
    key_topics: List[str]
    technical_details: List[str]
    timestamp: datetime


class PostData(BaseModel):
    """Collected data for post generation."""
    date: datetime
    git_commits: List[GitCommit] = []
    claude_conversations: List[ClaudeConversation] = []
    file_changes: List[dict] = []
    project_updates: Dict[str, dict] = {}


class GeneratedPost(BaseModel):
    """Generated post content."""
    content: str
    style: PostStyle
    language: PostLanguage = PostLanguage.CHINESE
    hashtags: List[str]
    word_count: int
    projects_mentioned: List[str]
    technical_keywords: List[str]
    metadata: dict = {}


# SQLAlchemy Models for persistence
class PostRecord(Base):
    """Database model for post records."""
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    generation_date = Column(DateTime, nullable=False)

    # Content
    content = Column(Text, nullable=False)
    style = Column(String(50), nullable=False)
    language = Column(String(10), default='zh')  # 'zh' or 'en'
    hashtags = Column(JSON)
    word_count = Column(Integer)

    # Metadata
    projects_mentioned = Column(JSON)
    technical_keywords = Column(JSON)
    source_data = Column(JSON)  # Stores collected data
    generation_metadata = Column(JSON)

    # Status
    status = Column(String(20), default=PostStatus.DRAFT.value)
    selected_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # Xiaohongshu
    xhs_post_id = Column(String(100), nullable=True)
    xhs_url = Column(String(500), nullable=True)

    # X.com (Twitter)
    twitter_post_id = Column(String(100), nullable=True)
    twitter_url = Column(String(500), nullable=True)
    twitter_published_at = Column(DateTime, nullable=True)

    # Scheduling
    scheduled_publish_at = Column(DateTime, nullable=True)  # When to publish (future)
    scheduled_platforms = Column(JSON, nullable=True)       # ["twitter", "xiaohongshu"]
    schedule_source = Column(String(50), nullable=True)     # "temp_post" or "daily_selected"

    # Analytics
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)


class GenerationLog(Base):
    """Log of generation attempts."""
    __tablename__ = 'generation_logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    date = Column(DateTime, nullable=False)
    posts_generated = Column(Integer)
    success = Column(Boolean)
    error_message = Column(Text, nullable=True)
    generation_metadata = Column(JSON)


# Database setup
def init_db():
    """Initialize database."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session():
    """Get database session."""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    return Session()
