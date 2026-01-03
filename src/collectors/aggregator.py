"""Data aggregator - combines all collected data."""

from datetime import datetime
from typing import Dict, List
from src.models import PostData, GitCommit, ClaudeConversation
from src.collectors.git_collector import GitCollector
from src.collectors.claude_collector import ClaudeCollector
from src.config import settings


class DataAggregator:
    """Aggregate data from all collectors."""

    def __init__(self, lookback_days: int = None):
        """Initialize aggregator.

        Args:
            lookback_days: Number of days to look back
        """
        self.lookback_days = lookback_days or settings.lookback_days
        self.git_collector = GitCollector(lookback_days=self.lookback_days)
        self.claude_collector = ClaudeCollector(lookback_days=self.lookback_days)

    def collect_all_data(self) -> PostData:
        """Collect all data for post generation.

        Returns:
            PostData object with all collected information
        """
        print("📦 Collecting data from all sources...\n")

        # Collect Git commits
        print("📊 Collecting Git commits...")
        git_commits = self.git_collector.collect_all()
        git_summary = self.git_collector.get_summary(git_commits)
        print(f"   ✅ Found {git_summary['total_commits']} commits")

        # Collect Claude conversations
        print("💬 Collecting Claude conversations...")
        claude_conversations = self.claude_collector.collect_all()
        claude_summary = self.claude_collector.get_summary(claude_conversations)
        print(f"   ✅ Found {claude_summary['total_sessions']} sessions")

        # Organize by project
        project_updates = self._organize_by_project(git_commits, claude_conversations)

        post_data = PostData(
            date=datetime.now(),
            git_commits=git_commits,
            claude_conversations=claude_conversations,
            project_updates=project_updates,
        )

        print(f"\n✨ Data collection complete!")
        print(f"   Projects with activity: {len(project_updates)}")

        return post_data

    def _organize_by_project(
        self,
        git_commits: List[GitCommit],
        claude_conversations: List[ClaudeConversation]
    ) -> Dict[str, dict]:
        """Organize data by project.

        Args:
            git_commits: List of git commits
            claude_conversations: List of Claude conversations

        Returns:
            Dictionary organized by project name
        """
        project_data = {}

        # Get project configs from settings (loaded from .env)
        project_configs = {p['name']: p for p in settings.all_projects}

        # Initialize all configured projects (even if no activity)
        for project_name, config in project_configs.items():
            project_data[project_name] = {
                "name": project_name,
                "type": config.get('type', 'unknown'),
                "description": config.get('description', ''),
                "commits": [],
                "conversations": [],
                "topics": set(),
                "commit_count": 0,
                "has_activity": False,
            }

        # Organize commits by project
        for commit in git_commits:
            if commit.project not in project_data:
                # Handle projects not in config
                project_data[commit.project] = {
                    "name": commit.project,
                    "type": 'unknown',
                    "description": '',
                    "commits": [],
                    "conversations": [],
                    "topics": set(),
                    "commit_count": 0,
                    "has_activity": False,
                }

            project_data[commit.project]["commits"].append(commit)
            project_data[commit.project]["commit_count"] += 1
            project_data[commit.project]["has_activity"] = True

        # Organize conversations by project
        for conv in claude_conversations:
            if conv.project not in project_data:
                # Handle projects not in config
                project_data[conv.project] = {
                    "name": conv.project,
                    "type": 'unknown',
                    "description": '',
                    "commits": [],
                    "conversations": [],
                    "topics": set(),
                    "commit_count": 0,
                    "has_activity": False,
                }

            project_data[conv.project]["conversations"].append(conv)
            project_data[conv.project]["topics"].update(conv.key_topics)
            project_data[conv.project]["has_activity"] = True

        # Convert topics set to list
        for project in project_data.values():
            project["topics"] = list(project["topics"])

        return project_data

    def get_highlights(self, post_data: PostData) -> Dict[str, any]:
        """Extract highlights from collected data.

        Args:
            post_data: Collected post data

        Returns:
            Dictionary with highlights
        """
        highlights = {
            "total_commits": len(post_data.git_commits),
            "active_projects": len(post_data.project_updates),
            "total_sessions": len(post_data.claude_conversations),
            "all_topics": set(),
            "major_updates": [],
        }

        # Collect all topics
        for project_data in post_data.project_updates.values():
            highlights["all_topics"].update(project_data.get("topics", []))

        # Find major updates (projects with 3+ commits)
        for project_name, project_data in post_data.project_updates.items():
            if project_data["commit_count"] >= 3:
                highlights["major_updates"].append({
                    "project": project_name,
                    "commits": project_data["commit_count"],
                    "description": project_data.get("description", ""),
                })

        highlights["all_topics"] = list(highlights["all_topics"])

        return highlights


if __name__ == "__main__":
    # Test aggregator
    aggregator = DataAggregator(lookback_days=7)
    data = aggregator.collect_all_data()

    print("\n" + "=" * 60)
    print("📋 COLLECTED DATA SUMMARY")
    print("=" * 60)

    highlights = aggregator.get_highlights(data)

    print(f"\n📊 Statistics:")
    print(f"   Total commits: {highlights['total_commits']}")
    print(f"   Active projects: {highlights['active_projects']}")
    print(f"   Claude sessions: {highlights['total_sessions']}")

    print(f"\n🔥 Major Updates:")
    for update in highlights['major_updates']:
        print(f"   • {update['project']}: {update['commits']} commits")

    print(f"\n🏷️  Topics: {', '.join(highlights['all_topics'][:10])}")

    print(f"\n📁 Projects with activity:")
    for project_name, project_data in data.project_updates.items():
        print(f"   • {project_name}: {project_data['commit_count']} commits, {len(project_data['conversations'])} sessions")
