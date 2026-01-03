"""AI Agent Manager - Morning Meeting System.

This module provides the morning meeting functionality for coordinating
multiple AI agents and projects. It collects data from all projects,
reviews yesterday's accomplishments, extracts today's tasks, and tracks
weekly goals.
"""

import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from src.config import settings


@dataclass
class ProjectStatus:
    """Status of a single project."""
    name: str
    path: str
    yesterday_commits: List[Dict[str, str]] = field(default_factory=list)
    today_tasks: List[Dict[str, str]] = field(default_factory=list)
    weekly_goals: List[str] = field(default_factory=list)
    current_phase: str = ""
    health: str = "🟢"  # 🟢 On Track / 🟡 At Risk / 🔴 Blocked
    blockers: List[str] = field(default_factory=list)
    launch_plan_file: Optional[str] = None


@dataclass
class MeetingReport:
    """Complete morning meeting report."""
    date: datetime
    projects: List[ProjectStatus]
    ai_workflows: Dict[str, str]
    cross_project_dependencies: List[str] = field(default_factory=list)
    decisions_needed: List[str] = field(default_factory=list)


class MeetingManager:
    """Manages the morning meeting workflow for AI Agent coordination."""

    # Project configurations loaded from config
    # Configure your projects in config/projects.yaml or .env file
    PROJECTS = {}

    @classmethod
    def _load_projects(cls) -> Dict[str, Dict]:
        """Load project configurations from settings.

        Returns:
            Dictionary of project name -> project config
        """
        if not cls.PROJECTS:
            agent_num = 1
            for project in settings.all_projects:
                is_public = project.get("public", True)
                cls.PROJECTS[project["name"]] = {
                    "path": project["path"],
                    "agent": f"Claude Agent #{agent_num}",
                    "description": project.get("description", f"{project['name']} project"),
                    "public": is_public
                }
                agent_num += 1
        return cls.PROJECTS

    # AI Workflow definitions
    AI_WORKFLOWS = {
        "image_video": {
            "name": "Image/Video Content",
            "flow": "Source file/prompt → NanoBanana Pro → Affinity (human review) → Final asset",
            "tools": ["NanoBanana Pro", "Affinity Designer/Photo"]
        },
        "text_content": {
            "name": "Text Content (Posts)",
            "flow": "Requirement (todos.md) → build-in-public (Claude) → Post",
            "tools": ["Claude", "Build-in-Public Posting Tool"]
        },
        "planning": {
            "name": "Planning & Scheduling",
            "flow": "Complex task → Project's Claude session → Structured plan",
            "tools": ["Claude (project-specific)"]
        },
        "infographics": {
            "name": "Infographics/PPT",
            "flow": "User prompt + source files → NotebookLM → Result",
            "tools": ["NotebookLM"]
        },
        "debugging": {
            "name": "Debugging & Research",
            "flow": "Issue → Gemini (quick) → Claude (deep) → Human (if blocked)",
            "tools": ["Gemini", "Claude"]
        },
        "video_production": {
            "name": "Video Production",
            "flow": "Video script → Key frames prompts → NanoBanana Pro (key frames) → Veo 3.1 (frame mode) → Connect for final result",
            "tools": ["NanoBanana Pro", "Veo 3.1"]
        }
    }

    def __init__(self):
        """Initialize the meeting manager."""
        self.report_dir = Path(settings.base_dir) / "data" / "meetings"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def get_yesterday_commits(self, project_path: str, days: int = 1) -> List[Dict[str, str]]:
        """Get git commits from yesterday (or specified days back).

        Args:
            project_path: Path to the git repository
            days: Number of days to look back

        Returns:
            List of commit dictionaries with hash, message, author, date
        """
        commits = []
        try:
            # Get commits from the last N days
            since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cmd = [
                "git", "-C", project_path, "log",
                f"--since={since_date}",
                "--pretty=format:%h|%s|%an|%ar",
                "--no-merges"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|')
                        if len(parts) >= 4:
                            commits.append({
                                "hash": parts[0],
                                "message": parts[1],
                                "author": parts[2],
                                "date": parts[3]
                            })
        except Exception as e:
            print(f"  ⚠️  Error getting commits for {project_path}: {e}")

        return commits

    def find_launch_plan(self, project_path: str) -> Optional[Path]:
        """Find the launch plan file in a project.

        Args:
            project_path: Path to the project directory

        Returns:
            Path to launch plan file or None
        """
        project_dir = Path(project_path)
        if not project_dir.exists():
            return None

        # Search for files containing both "launch" and "plan" (case-insensitive)
        for file_path in project_dir.rglob("*.md"):
            filename_lower = file_path.name.lower()
            if "launch" in filename_lower and "plan" in filename_lower:
                # Skip archived files
                if "_archived_" in str(file_path):
                    continue
                return file_path

        return None

    def extract_today_tasks(self, launch_plan_path: Path) -> List[Dict[str, str]]:
        """Extract today's tasks from a launch plan file.

        Args:
            launch_plan_path: Path to the launch plan markdown file

        Returns:
            List of task dictionaries with title, duration, priority
        """
        tasks = []
        today = datetime.now()
        # Use %-d for day without leading zero on Linux, or fallback for Windows
        try:
            today_str = today.strftime("%b %-d").lower()  # e.g., "dec 1" (no leading zero)
        except ValueError:
            # Windows doesn't support %-d, use %#d instead or strip leading zero
            today_str = today.strftime("%b %d").lower().replace(" 0", " ")  # e.g., "dec 1"
        today_str_alt = today.strftime("%-m/%d") if hasattr(today, 'strftime') else f"{today.month}/{today.day}"  # e.g., "12/1"

        try:
            with open(launch_plan_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return tasks

        lines = content.split('\n')
        current_day_date = None
        is_today = False

        for line in lines:
            # Check for day header like "**Day 22 (Dec 1 - Mon)**" or "**Day 25 (Dec 4 - Thu) 小夜班** - 2 hours:"
            # The pattern captures the date part inside parentheses, allowing for additional text after
            day_header_match = re.match(r'^\*\*Day\s+(\d+)\s*\(([^)]+)\)', line, re.IGNORECASE)
            if day_header_match:
                day_num = day_header_match.group(1)
                date_part = day_header_match.group(2).lower()
                # Check if this is today - match "dec 4" format
                is_today = today_str in date_part or today.strftime("%B %d").lower() in date_part
                continue

            if not is_today:
                continue

            # Skip completed tasks
            completion_markers = ['✅', 'done]', '[done', 'moved', 'postponed', 'skipped', '❌', '[x]', '[X]']
            if any(marker.lower() in line.lower() for marker in completion_markers):
                continue

            # Look for incomplete tasks
            task_match = re.match(r'^\s*[-*]?\s*\[\s*\]\s*(.+)$', line)
            if task_match:
                task_title = task_match.group(1).strip()
                if len(task_title) < 10:
                    continue

                # Parse duration
                duration = "1h"
                duration_match = re.search(r'\((\d+\.?\d*)\s*h(?:our)?s?\)', task_title, re.IGNORECASE)
                if duration_match:
                    duration = f"{duration_match.group(1)}h"

                # Clean title
                clean_title = re.sub(r'\s*\([^)]*h(?:our)?s?\)', '', task_title)
                clean_title = re.sub(r'^\*\*BACKLOG\s*\([^)]*\)\*\*\s*:\s*', '', clean_title)
                clean_title = re.sub(r'^\*\*|\*\*$', '', clean_title)
                clean_title = clean_title.strip()

                # Determine priority
                priority = "P1"
                if "PRIORITY" in task_title.upper() or "BACKLOG" in task_title.upper():
                    priority = "P0"

                tasks.append({
                    "title": clean_title[:100],
                    "duration": duration,
                    "priority": priority
                })

        return tasks

    def extract_weekly_goals(self, launch_plan_path: Path) -> List[str]:
        """Extract this week's goals from a launch plan file.

        Args:
            launch_plan_path: Path to the launch plan markdown file

        Returns:
            List of weekly goal strings
        """
        goals = []
        today = datetime.now()

        # Calculate current week number and date range
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        try:
            with open(launch_plan_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return goals

        # Look for week headers like "### WEEK 4 (Days 22-28, Dec 1-7)"
        week_pattern = r'###?\s*WEEK\s*(\d+)[^#]*?(?=###?\s*WEEK|\Z)'
        week_matches = re.findall(week_pattern, content, re.IGNORECASE | re.DOTALL)

        # Also look for deliverables
        deliverable_pattern = r'\*\*Week\s*\d+\s*(?:Deliverable|Goal|Total)[^*]*\*\*:?\s*([^\n]+)'
        deliverables = re.findall(deliverable_pattern, content, re.IGNORECASE)
        goals.extend([d.strip() for d in deliverables if d.strip()])

        return goals[:5]  # Limit to 5 goals

    def detect_blockers(self, project_path: str, launch_plan_path: Optional[Path]) -> List[str]:
        """Detect potential blockers for a project.

        Args:
            project_path: Path to the project
            launch_plan_path: Path to launch plan file

        Returns:
            List of blocker descriptions
        """
        blockers = []

        if launch_plan_path:
            try:
                with open(launch_plan_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Look for blocked markers
                blocked_patterns = [
                    r'\[⏸️\s*BLOCKED\][^\n]+',
                    r'\*\*BLOCKED\*\*[^\n]+',
                    r'🔴[^\n]+blocked[^\n]*',
                ]
                for pattern in blocked_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    blockers.extend([m.strip()[:100] for m in matches])

            except Exception:
                pass

        return blockers[:5]  # Limit

    def determine_health(self, commits: List, tasks: List, blockers: List) -> str:
        """Determine project health status.

        Args:
            commits: Yesterday's commits
            tasks: Today's tasks
            blockers: Known blockers

        Returns:
            Health emoji: 🟢 On Track / 🟡 At Risk / 🔴 Blocked
        """
        if blockers:
            return "🔴 Blocked"
        if not commits and not tasks:
            return "🟡 At Risk"
        return "🟢 On Track"

    def collect_project_status(self, project_name: str, project_config: Dict) -> ProjectStatus:
        """Collect complete status for a single project.

        Args:
            project_name: Name of the project
            project_config: Project configuration dictionary

        Returns:
            ProjectStatus dataclass
        """
        project_path = project_config["path"]

        # Find launch plan
        launch_plan = self.find_launch_plan(project_path)

        # Get yesterday's commits
        commits = self.get_yesterday_commits(project_path)

        # Get today's tasks
        tasks = []
        if launch_plan:
            tasks = self.extract_today_tasks(launch_plan)

        # Get weekly goals
        goals = []
        if launch_plan:
            goals = self.extract_weekly_goals(launch_plan)

        # Detect blockers
        blockers = self.detect_blockers(project_path, launch_plan)

        # Determine health
        health = self.determine_health(commits, tasks, blockers)

        return ProjectStatus(
            name=project_name,
            path=project_path,
            yesterday_commits=commits,
            today_tasks=tasks,
            weekly_goals=goals,
            current_phase=project_config.get("description", ""),
            health=health,
            blockers=blockers,
            launch_plan_file=str(launch_plan) if launch_plan else None
        )

    def generate_meeting_report(self) -> MeetingReport:
        """Generate a complete morning meeting report.

        Returns:
            MeetingReport dataclass with all project statuses
        """
        print("📊 Collecting project statuses...")

        # Load projects from config
        project_configs = self._load_projects()

        projects = []
        for name, config in project_configs.items():
            print(f"  📁 {name}...")
            status = self.collect_project_status(name, config)
            projects.append(status)

        return MeetingReport(
            date=datetime.now(),
            projects=projects,
            ai_workflows=self.AI_WORKFLOWS
        )

    def format_report_text(self, report: MeetingReport) -> str:
        """Format the meeting report as readable text.

        Args:
            report: MeetingReport to format

        Returns:
            Formatted text string
        """
        lines = []
        lines.append("=" * 70)
        lines.append(f"🌅 MORNING MEETING REPORT - {report.date.strftime('%Y-%m-%d %A')}")
        lines.append("=" * 70)
        lines.append("")

        # Section 1: Yesterday's Accomplishments
        lines.append("## 📋 YESTERDAY'S ACCOMPLISHMENTS")
        lines.append("-" * 40)

        total_commits = 0
        for project in report.projects:
            lines.append(f"\n### {project.name}")
            if project.yesterday_commits:
                for commit in project.yesterday_commits[:5]:
                    lines.append(f"  ✅ {commit['message']} ({commit['date']})")
                    total_commits += 1
            else:
                lines.append("  (No commits yesterday)")

        lines.append(f"\n📊 Total commits: {total_commits}")
        lines.append("")

        # Section 2: Project Health Overview
        lines.append("## 🏥 PROJECT HEALTH OVERVIEW")
        lines.append("-" * 40)

        for project in report.projects:
            lines.append(f"\n### {project.name} - {project.health}")
            lines.append(f"  📝 {project.current_phase}")
            if project.launch_plan_file:
                lines.append(f"  📄 Launch Plan: {Path(project.launch_plan_file).name}")
            if project.blockers:
                lines.append("  ⚠️ Blockers:")
                for blocker in project.blockers:
                    lines.append(f"    - {blocker}")
        lines.append("")

        # Section 3: Today's Tasks
        lines.append("## 📌 TODAY'S TASKS")
        lines.append("-" * 40)

        total_tasks = 0
        for project in report.projects:
            if project.today_tasks:
                lines.append(f"\n### {project.name}")
                for task in project.today_tasks:
                    lines.append(f"  [ ] [{task['priority']}] {task['title']} ({task['duration']})")
                    total_tasks += 1

        if total_tasks == 0:
            lines.append("\n  (No tasks scheduled for today - check launch plans)")
        else:
            lines.append(f"\n📊 Total tasks: {total_tasks}")
        lines.append("")

        # Section 4: Weekly Goals
        lines.append("## 🎯 THIS WEEK'S GOALS")
        lines.append("-" * 40)

        for project in report.projects:
            if project.weekly_goals:
                lines.append(f"\n### {project.name}")
                for goal in project.weekly_goals:
                    lines.append(f"  • {goal}")
        lines.append("")

        # Section 5: AI Workflows Reference
        lines.append("## 🤖 AI WORKFLOWS REFERENCE")
        lines.append("-" * 40)

        for key, workflow in report.ai_workflows.items():
            lines.append(f"\n**{workflow['name']}**")
            lines.append(f"  {workflow['flow']}")
        lines.append("")

        # Section 6: Agent Assignments
        lines.append("## 👥 AGENT ASSIGNMENTS")
        lines.append("-" * 40)

        # Load projects from config
        project_configs = self._load_projects()

        for project in report.projects:
            agent = project_configs.get(project.name, {}).get("agent", "Unknown")
            lines.append(f"\n**{agent}** → {project.name}")
            if project.today_tasks:
                lines.append(f"  Tasks: {len(project.today_tasks)} items")
            else:
                lines.append("  Tasks: Review launch plan and define priorities")
        lines.append("")

        lines.append("=" * 70)
        lines.append("🚀 Have a productive day!")
        lines.append("=" * 70)

        return "\n".join(lines)

    def save_report(self, report: MeetingReport, text: str) -> Path:
        """Save the meeting report to a file.

        Args:
            report: MeetingReport object
            text: Formatted text content

        Returns:
            Path to saved file
        """
        filename = f"meeting_{report.date.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.report_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)

        return filepath

    def run_meeting(self) -> Tuple[MeetingReport, str, Path]:
        """Run the complete morning meeting workflow.

        Returns:
            Tuple of (MeetingReport, formatted_text, saved_file_path)
        """
        print("\n🌅 Starting Morning Meeting...")
        print("=" * 50)

        # Generate report
        report = self.generate_meeting_report()

        # Format as text
        text = self.format_report_text(report)

        # Save to file
        filepath = self.save_report(report, text)

        print(f"\n✅ Meeting report saved to: {filepath}")

        return report, text, filepath


if __name__ == "__main__":
    manager = MeetingManager()
    report, text, filepath = manager.run_meeting()
    print("\n" + text)
