"""Claude Code conversation collector."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import re

from src.models import ClaudeConversation
from src.config import settings, bip_settings


class ClaudeCollector:
    """Collect Claude Code conversation history."""

    def __init__(self, lookback_days: int = None):
        """Initialize collector.

        Args:
            lookback_days: Number of days to look back
        """
        self.lookback_days = lookback_days or settings.lookback_days
        self.projects = settings.projects

        # Find Claude projects directory
        # Try multiple possible locations (Windows vs Linux)
        possible_dirs = [
            Path.home() / ".claude" / "projects",  # Linux/WSL
            Path("C:/Users") / os.environ.get("USERNAME", "") / ".claude" / "projects",  # Windows
            Path("/home") / os.environ.get("USER", "") / ".claude" / "projects",  # WSL from Windows
        ]

        self.central_claude_dir = None
        for dir_path in possible_dirs:
            if dir_path.exists():
                self.central_claude_dir = dir_path
                break

    def _get_project_claude_dir(self, project_path: str) -> Path:
        """Get .claude directory for a project.

        Args:
            project_path: Path to project

        Returns:
            Path to project's .claude directory
        """
        # Claude conversations are stored in project_path/.claude
        # e.g., ../4to1-planner-dev/.claude
        abs_path = (Path(settings.base_dir) / project_path).resolve()
        claude_dir = abs_path / ".claude"

        return claude_dir

    def _get_central_claude_dir(self, project_path: str) -> Path:
        """Get centralized Claude session directory for a project.

        Args:
            project_path: Path to project

        Returns:
            Path to Claude sessions directory in ~/.claude/projects/
        """
        abs_path = (Path(settings.base_dir) / project_path).resolve()
        abs_path_str = str(abs_path)

        # Convert Windows path to WSL format if needed
        import re
        if re.match(r'^[A-Za-z]:\\', abs_path_str):
            drive_letter = abs_path_str[0].lower()
            path_remainder = abs_path_str[3:].replace('\\', '/')
            abs_path_str = f'/mnt/{drive_letter}/{path_remainder}'

        # Replace slashes and underscores with dashes
        normalized_path = abs_path_str.replace("/", "-").replace("_", "-")

        # Use string concatenation to avoid Path issues with leading dash
        target_path = Path(str(self.central_claude_dir) + "/" + normalized_path)

        return target_path

    def parse_jsonl_session(self, session_file: Path) -> List[dict]:
        """Parse a JSONL session file.

        Args:
            session_file: Path to .jsonl file

        Returns:
            List of message objects
        """
        messages = []

        if not session_file.exists():
            return messages

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            messages.append(msg)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"⚠️  Error reading {session_file}: {e}")

        return messages

    def extract_key_info(self, messages: List[dict]) -> dict:
        """Extract key information from messages.

        Args:
            messages: List of message objects

        Returns:
            Dictionary with extracted info
        """
        user_questions = []
        technical_details = []
        topics = set()

        for msg in messages:
            # Extract user messages
            if msg.get('type') == 'user':
                content = msg.get('message', {}).get('content', '')
                if isinstance(content, str) and content:
                    user_questions.append(content[:200])  # First 200 chars
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            user_questions.append(item.get('text', '')[:200])

            # Extract assistant thinking blocks
            if msg.get('type') == 'assistant':
                content = msg.get('message', {}).get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get('type') == 'thinking':
                                thinking = item.get('thinking', '')
                                if thinking:
                                    # Extract key technical terms (from config)
                                    tech_keywords = bip_settings.tech_keywords
                                    pattern = r'\b(' + '|'.join(re.escape(k) for k in tech_keywords) + r')\b'
                                    tech_terms = re.findall(pattern, thinking, re.IGNORECASE)
                                    topics.update(tech_terms)

                            if item.get('type') == 'text':
                                text = item.get('text', '')
                                # Extract code blocks or technical explanations
                                if '```' in text or 'function' in text or 'class' in text:
                                    technical_details.append(text[:300])

        return {
            "user_questions": user_questions[:5],  # Top 5 questions
            "technical_details": technical_details[:5],  # Top 5 technical items
            "topics": list(topics)[:10],  # Top 10 topics
        }

    def collect_conversations(self, project_path: str, project_name: str) -> List[ClaudeConversation]:
        """Collect conversations for a project.

        Args:
            project_path: Path to project
            project_name: Name of project

        Returns:
            List of ClaudeConversation objects
        """
        conversations = []
        since_date = datetime.now() - timedelta(days=self.lookback_days)

        # Check both locations:
        # 1. Centralized Claude projects directory (~/.claude/projects/)
        # 2. Project's local .claude directory

        # Try centralized directory first (live JSONL files)
        if self.central_claude_dir:
            central_dir = self._get_central_claude_dir(project_path)
        else:
            central_dir = None

        if central_dir and central_dir.exists() and os.path.isdir(str(central_dir)):
            try:
                # Use os.listdir to handle directories with leading dash
                for filename in os.listdir(str(central_dir)):
                    if not filename.endswith('.jsonl'):
                        continue

                    # Skip agent files
                    if filename.startswith("agent-"):
                        continue

                    session_file_path = os.path.join(str(central_dir), filename)
                    session_file = Path(session_file_path)

                    # Check modification time
                    mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                    if mtime < since_date:
                        continue

                    # Parse session
                    messages = self.parse_jsonl_session(session_file)
                    if not messages:
                        continue

                    # Extract key info
                    key_info = self.extract_key_info(messages)

                    conversations.append(
                        ClaudeConversation(
                            session_id=session_file.stem,
                            project=project_name,
                            messages=messages[-20:],  # Keep last 20 messages for context
                            key_topics=key_info['topics'],
                            technical_details=key_info['technical_details'],
                            timestamp=mtime,
                        )
                    )
            except Exception as e:
                print(f"⚠️  Error reading centralized conversations from {project_name}: {e}")

        # Also try project's local .claude directory (may have exported JSONLs)
        local_claude_dir = self._get_project_claude_dir(project_path)
        if local_claude_dir.exists():
            try:
                for session_file in local_claude_dir.glob("*.jsonl"):
                    # Skip agent files
                    if session_file.name.startswith("agent-"):
                        continue

                    # Check modification time
                    mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                    if mtime < since_date:
                        continue

                    # Parse session
                    messages = self.parse_jsonl_session(session_file)
                    if not messages:
                        continue

                    # Extract key info
                    key_info = self.extract_key_info(messages)

                    # Avoid duplicates
                    session_id = session_file.stem
                    if any(c.session_id == session_id for c in conversations):
                        continue

                    conversations.append(
                        ClaudeConversation(
                            session_id=session_id,
                            project=project_name,
                            messages=messages[-20:],  # Keep last 20 messages for context
                            key_topics=key_info['topics'],
                            technical_details=key_info['technical_details'],
                            timestamp=mtime,
                        )
                    )
            except Exception as e:
                print(f"⚠️  Error reading local conversations from {project_name}: {e}")

        return conversations

    def collect_all(self) -> List[ClaudeConversation]:
        """Collect conversations from all monitored projects.

        Returns:
            List of all ClaudeConversation objects
        """
        all_conversations = []

        for project in self.projects:
            project_conversations = self.collect_conversations(
                project['path'],
                project['name']
            )
            all_conversations.extend(project_conversations)

        # Sort by timestamp descending
        all_conversations.sort(key=lambda x: x.timestamp, reverse=True)

        return all_conversations

    def get_summary(self, conversations: List[ClaudeConversation]) -> dict:
        """Get summary statistics.

        Args:
            conversations: List of conversations

        Returns:
            Summary dictionary
        """
        if not conversations:
            return {
                "total_sessions": 0,
                "projects": {},
                "all_topics": [],
            }

        project_counts = {}
        all_topics = set()

        for conv in conversations:
            project_counts[conv.project] = project_counts.get(conv.project, 0) + 1
            all_topics.update(conv.key_topics)

        return {
            "total_sessions": len(conversations),
            "projects": project_counts,
            "all_topics": list(all_topics),
            "latest_activity": conversations[0].timestamp if conversations else None,
        }


if __name__ == "__main__":
    # Test the collector
    collector = ClaudeCollector(lookback_days=7)
    conversations = collector.collect_all()

    print(f"\n💬 Collected {len(conversations)} Claude sessions from past 7 days\n")

    for conv in conversations[:3]:  # Show first 3
        print(f"[{conv.project}] Session: {conv.session_id}")
        print(f"   Topics: {', '.join(conv.key_topics[:5])}")
        print(f"   Messages: {len(conv.messages)}\n")

    summary = collector.get_summary(conversations)
    print(f"\n📈 Summary:")
    print(f"   Total: {summary['total_sessions']} sessions")
    for project, count in summary['projects'].items():
        print(f"   {project}: {count} sessions")
    print(f"   Topics: {', '.join(summary['all_topics'][:10])}")
