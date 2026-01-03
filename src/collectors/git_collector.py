"""Git commit collector."""

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from git import Repo, InvalidGitRepositoryError

from src.models import GitCommit
from src.config import settings


class GitCollector:
    """Collect Git commit information from monitored projects."""

    def __init__(self, lookback_days: int = None):
        """Initialize collector.

        Args:
            lookback_days: Number of days to look back for commits
        """
        self.lookback_days = lookback_days or settings.lookback_days
        self.projects = settings.projects

    def _collect_commits_via_subprocess(self, project_path: str, project_name: str) -> List[GitCommit]:
        """Collect commits using subprocess git command (Windows fallback).

        Args:
            project_path: Path to project repository
            project_name: Name of the project

        Returns:
            List of GitCommit objects
        """
        commits = []
        abs_path = Path(settings.base_dir) / project_path

        if not abs_path.exists():
            return commits

        # Calculate since date
        since_date = datetime.now() - timedelta(days=self.lookback_days)
        since_str = since_date.strftime("%Y-%m-%d")

        try:
            # Use git log command directly
            result = subprocess.run(
                ['git', 'log', f'--since={since_str}', '--no-merges',
                 '--pretty=format:%H|%an|%ct|%s'],
                cwd=str(abs_path),
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|', 3)
                        if len(parts) == 4:
                            hash_full, author, timestamp, message = parts
                            commits.append(
                                GitCommit(
                                    hash=hash_full[:7],
                                    message=message.strip(),
                                    author=author,
                                    timestamp=datetime.fromtimestamp(int(timestamp)),
                                    project=project_name,
                                )
                            )
        except Exception as e:
            print(f"⚠️  Could not read commits from {project_name}: {str(e)[:80]}")

        return commits

    def collect_commits(self, project_path: str, project_name: str) -> List[GitCommit]:
        """Collect commits from a project.

        Args:
            project_path: Path to project repository
            project_name: Name of the project

        Returns:
            List of GitCommit objects
        """
        commits = []

        # Resolve path
        abs_path = Path(settings.base_dir) / project_path

        if not abs_path.exists():
            print(f"⚠️  Project path does not exist: {abs_path}")
            return commits

        try:
            repo = Repo(abs_path)
        except InvalidGitRepositoryError:
            print(f"⚠️  Not a valid git repository: {abs_path}")
            return commits

        # Calculate since date
        since_date = datetime.now() - timedelta(days=self.lookback_days)

        # Get commits
        try:
            # Try to get all commits and filter by date manually
            # This is more robust than using since parameter on Windows
            all_commits = list(repo.iter_commits(max_count=100, no_merges=True))

            for commit in all_commits:
                commit_date = datetime.fromtimestamp(commit.committed_date)

                # Only include commits within lookback period
                if commit_date >= since_date:
                    commits.append(
                        GitCommit(
                            hash=commit.hexsha[:7],
                            message=commit.message.strip(),
                            author=commit.author.name,
                            timestamp=commit_date,
                            project=project_name,
                        )
                    )
        except (ValueError, Exception) as e:
            # GitPython failed, try subprocess fallback
            print(f"   ⚡ Using git command fallback for {project_name}...")
            commits = self._collect_commits_via_subprocess(project_path, project_name)
            if not commits:
                print(f"   ⚠️  No commits found (GitPython error: {str(e)[:50]})")
            return commits

        return commits

    def collect_all(self) -> List[GitCommit]:
        """Collect commits from all monitored projects.

        Returns:
            List of all GitCommit objects
        """
        all_commits = []

        for project in self.projects:
            project_commits = self.collect_commits(
                project['path'],
                project['name']
            )
            all_commits.extend(project_commits)

        # Sort by timestamp descending
        all_commits.sort(key=lambda x: x.timestamp, reverse=True)

        return all_commits

    def get_summary(self, commits: List[GitCommit]) -> dict:
        """Get summary statistics.

        Args:
            commits: List of commits

        Returns:
            Summary dictionary
        """
        if not commits:
            return {
                "total_commits": 0,
                "projects": {},
                "date_range": None,
            }

        project_counts = {}
        for commit in commits:
            project_counts[commit.project] = project_counts.get(commit.project, 0) + 1

        return {
            "total_commits": len(commits),
            "projects": project_counts,
            "date_range": {
                "from": min(c.timestamp for c in commits),
                "to": max(c.timestamp for c in commits),
            },
            "latest_commit": commits[0].timestamp if commits else None,
        }


if __name__ == "__main__":
    # Test the collector
    collector = GitCollector(lookback_days=7)
    commits = collector.collect_all()

    print(f"\n📊 Collected {len(commits)} commits from past 7 days\n")

    for commit in commits[:10]:  # Show first 10
        print(f"[{commit.project}] {commit.hash} - {commit.message[:60]}...")

    summary = collector.get_summary(commits)
    print(f"\n📈 Summary:")
    print(f"   Total: {summary['total_commits']} commits")
    for project, count in summary['projects'].items():
        print(f"   {project}: {count} commits")
