"""ICS Calendar generator for extracting tasks with dates from project todos."""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import uuid

from src.config import settings


@dataclass
class CalendarTask:
    """Represents a task with date for the calendar."""
    project: str
    title: str
    date: datetime
    duration_hours: float = 1.0  # Default 1 hour
    source_file: str = ""


class CalendarGenerator:
    """Generate ICS calendar files from project todos."""

    # Project directories loaded from config (settings.all_projects)
    # Configure your projects in config/projects.yaml or .env file
    PROJECT_DIRS = {}

    @classmethod
    def _load_project_dirs(cls) -> Dict[str, str]:
        """Load project directories from config."""
        if not cls.PROJECT_DIRS:
            for project in settings.all_projects:
                cls.PROJECT_DIRS[project["name"]] = project["path"]
        return cls.PROJECT_DIRS

    # Plans directory name (inside each project)
    PLANS_DIR = "plans"

    def __init__(self, output_dir: str = "data"):
        """Initialize the calendar generator.

        Args:
            output_dir: Directory to save the ICS file
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load work hours from settings (Tier 2)
        self.TIMEZONE = settings.timezone
        self.WORK_START_HOUR = settings.calendar_work_start_hour
        self.LUNCH_START = settings.calendar_lunch_start
        self.LUNCH_END = settings.calendar_lunch_end
        self.GAP_MINUTES = settings.calendar_gap_minutes

    def find_markdown_files(self) -> Dict[str, List[Path]]:
        """Find all markdown files inside plans/ directory of each project.

        Searches for a 'plans' directory inside each monitored project,
        and loads ALL .md files found there (no filename pattern matching).

        Returns:
            Dictionary of project name -> list of matching files
        """
        result = {}

        # Load project directories from config
        project_dirs = self._load_project_dirs()

        for project_name, project_path in project_dirs.items():
            project_dir = Path(project_path)
            matching_files = []

            if not project_dir.exists():
                print(f"  ⚠️  Project directory not found: {project_path}")
                continue

            # Look for plans/ directory inside the project
            plans_dir = project_dir / self.PLANS_DIR

            if not plans_dir.exists():
                print(f"  ℹ️  {project_name}: No '{self.PLANS_DIR}/' directory found")
                continue

            # Load ALL .md files from plans/ directory (no filename pattern)
            for file_path in plans_dir.rglob("*.md"):
                # Skip archived files
                if "_archived_" in str(file_path):
                    continue
                if file_path not in matching_files:
                    matching_files.append(file_path)

            if matching_files:
                result[project_name] = matching_files
                print(f"  📁 {project_name}: Found {len(matching_files)} file(s) in {self.PLANS_DIR}/")
                for f in matching_files:
                    print(f"      - {f.relative_to(plans_dir)}")
            else:
                print(f"  ℹ️  {project_name}: No .md files in '{self.PLANS_DIR}/' directory")

        return result

    def parse_duration(self, text: str) -> float:
        """Parse duration from text like '0.5h', '1h', '30min', etc.

        Args:
            text: Text potentially containing duration

        Returns:
            Duration in hours (default 1.0)
        """
        # Match patterns like "0.5h", "1h", "2h", "30min", "45min"
        hour_match = re.search(r'(\d+\.?\d*)\s*h(?:our)?s?\b', text, re.IGNORECASE)
        min_match = re.search(r'(\d+)\s*min(?:ute)?s?\b', text, re.IGNORECASE)

        if hour_match:
            return float(hour_match.group(1))
        elif min_match:
            return int(min_match.group(1)) / 60.0

        return 1.0  # Default 1 hour

    def parse_date(self, text: str) -> Optional[datetime]:
        """Parse date from text.

        Supports formats like:
        - 2025-11-20
        - November 20, 2025
        - Nov 20, 2025
        - 11/20/2025
        - 20/11/2025
        - Day 9 (Nov 18, 2025)

        Args:
            text: Text potentially containing a date

        Returns:
            datetime object or None if no date found
        """
        # Common date patterns
        patterns = [
            # 2025-11-20
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
            # November 20, 2025 or Nov 20, 2025
            (r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s*(\d{4})',
             lambda m: self._parse_month_day_year(m.group(1), int(m.group(2)), int(m.group(3)))),
            # 11/20/2025 (US format)
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))),
        ]

        for pattern, parser in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return parser(match)
                except (ValueError, AttributeError):
                    continue

        return None

    def _parse_month_day_year(self, month_str: str, day: int, year: int) -> datetime:
        """Parse month name to datetime."""
        month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        month = month_map.get(month_str.lower(), 1)
        return datetime(year, month, day)

    def extract_tasks_from_file(self, file_path: Path, project_name: str) -> List[CalendarTask]:
        """Extract tasks with dates from a markdown file.

        Only extracts INCOMPLETE tasks that have explicit date references.
        Skips completed tasks, references, URLs, and general documentation.

        Supports task formats:
        - [ ] task (standard markdown checkbox)
        - [] task (no space in checkbox)
        - []1. task (numbered task)
        - - [ ] task (with leading dash)

        Date formats supported:
        - Standalone: 2026-1-3, 2026-01-03, 2026/1/3
        - Day headers: **Day 22 (Dec 1 - Mon)** - 3 hours:
        - Markdown headers: ### Day 22 (December 1, 2025)

        Args:
            file_path: Path to the markdown file
            project_name: Name of the project

        Returns:
            List of CalendarTask objects
        """
        tasks = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ⚠️  Error reading {file_path}: {e}")
            return tasks

        # Split by lines
        lines = content.split('\n')

        # Track current day date from headers or standalone date lines
        current_day_date = None

        for i, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                continue

            # Check for standalone date line: 2026-1-3, 2026-01-03, 2026/1/3
            standalone_date_match = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*$', line.strip())
            if standalone_date_match:
                try:
                    year = int(standalone_date_match.group(1))
                    month = int(standalone_date_match.group(2))
                    day = int(standalone_date_match.group(3))
                    current_day_date = datetime(year, month, day)
                    continue
                except ValueError:
                    pass

            # Check for day header patterns like:
            # **Day 22 (Dec 1 - Mon)** - 3 hours:
            # **Day 22 (Dec 1)** - 3 hours:
            day_header_match = re.match(r'^\*\*Day\s+\d+\s*\(([^)]+)\)\*\*', line, re.IGNORECASE)
            if day_header_match:
                date_part = day_header_match.group(1)
                # Parse date like "Dec 1 - Mon" or "Dec 1" or "December 1, 2025"
                parsed_date = self._parse_day_header_date(date_part)
                if parsed_date:
                    current_day_date = parsed_date
                continue

            # Also check for markdown headers with dates
            if re.match(r'^#{1,6}\s+', line):
                header_date = self.parse_date(line)
                if header_date:
                    current_day_date = header_date
                continue

            # Skip if already marked as completed (various formats)
            completion_markers = ['✅', 'COMPLETED', '[x]', '[X]', 'done]', '[done', 'moved', 'postponed', 'skipped', '❌']
            line_lower = line.lower()
            if any(marker.lower() in line_lower for marker in completion_markers):
                continue

            # Skip URLs and references
            if 'http://' in line or 'https://' in line:
                continue

            # Look for INCOMPLETE checkbox tasks with various formats:
            # - [ ] task, [] task, []1. task, - [] task
            # Supports: [ ], [], with optional leading dash/asterisk, optional numbering after checkbox
            incomplete_match = re.match(r'^\s*[-*]?\s*\[\s*\]\s*\d*\.?\s*(.+)$', line)

            if not incomplete_match:
                continue

            task_title = incomplete_match.group(1).strip()

            # Skip if task title is too short
            if len(task_title) < 10:
                continue

            # Use the current day date from headers
            task_date = current_day_date

            # Only add task if we found a date
            if not task_date:
                continue

            # Skip past dates (only include today and future)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if task_date < today:
                continue

            # Parse duration from task text
            duration = self.parse_duration(task_title)

            # Clean up task title
            clean_title = re.sub(r'\s*[\(\[]\s*\d+\.?\d*\s*h(?:our)?s?\s*[\)\]]', '', task_title)
            clean_title = re.sub(r'\s*,?\s*\d+\.?\d*\s*h(?:our)?s?\s*$', '', clean_title)
            # Remove date from title if present
            clean_title = re.sub(r'\s*\(\s*\w+\s+\d+,?\s*\d{4}\s*\)', '', clean_title)
            clean_title = re.sub(r'\s*\d{4}-\d{2}-\d{2}\s*', '', clean_title)
            # Remove BACKLOG prefix (various formats) - do this BEFORE removing **
            # Format: **BACKLOG (2h)**: or **BACKLOG**: or BACKLOG:
            clean_title = re.sub(r'^\*\*BACKLOG\s*\([^)]*\)\*\*\s*:\s*', '', clean_title)
            clean_title = re.sub(r'^\*\*BACKLOG\*\*\s*:\s*', '', clean_title)
            clean_title = re.sub(r'^BACKLOG\s*\([^)]*\)\s*:\s*', '', clean_title)
            clean_title = re.sub(r'^BACKLOG\s*:\s*', '', clean_title)
            # Remove leading ** and trailing ** (bold markdown)
            clean_title = re.sub(r'^\*\*|\*\*$', '', clean_title)
            clean_title = clean_title.strip()

            if len(clean_title) < 5:
                continue

            tasks.append(CalendarTask(
                project=project_name,
                title=clean_title[:100],
                date=task_date,
                duration_hours=duration,
                source_file=str(file_path.name),
            ))

        return tasks

    def _parse_day_header_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from day header like 'Dec 1 - Mon' or 'Dec 1' or 'December 1, 2025'.

        Args:
            date_str: Date string from day header

        Returns:
            datetime object or None
        """
        # Remove day of week suffix like "- Mon", "- Tue", etc.
        date_str = re.sub(r'\s*-\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*$', '', date_str, flags=re.IGNORECASE)
        date_str = date_str.strip()

        # Try to parse "Dec 1" or "December 1" (assume current year or next year)
        month_day_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})', date_str, re.IGNORECASE)

        if month_day_match:
            month_str = month_day_match.group(1)
            day = int(month_day_match.group(2))

            month_map = {
                'january': 1, 'jan': 1,
                'february': 2, 'feb': 2,
                'march': 3, 'mar': 3,
                'april': 4, 'apr': 4,
                'may': 5,
                'june': 6, 'jun': 6,
                'july': 7, 'jul': 7,
                'august': 8, 'aug': 8,
                'september': 9, 'sep': 9,
                'october': 10, 'oct': 10,
                'november': 11, 'nov': 11,
                'december': 12, 'dec': 12,
            }

            month = month_map.get(month_str.lower())
            if month:
                # Check for year in the string
                year_match = re.search(r'(\d{4})', date_str)
                if year_match:
                    year = int(year_match.group(1))
                else:
                    # Use current year, or next year if month has passed
                    year = datetime.now().year
                    current_month = datetime.now().month
                    if month < current_month:
                        year += 1

                try:
                    return datetime(year, month, day)
                except ValueError:
                    pass

        return None

    def schedule_tasks(self, tasks: List[CalendarTask]) -> List[Tuple[CalendarTask, datetime, datetime]]:
        """Schedule tasks with proper timing.

        Schedules tasks starting at 9 AM Beijing time, with 20-minute gaps,
        skipping lunch break (12-14).

        Args:
            tasks: List of CalendarTask objects

        Returns:
            List of (task, start_time, end_time) tuples
        """
        # Group tasks by date
        tasks_by_date: Dict[str, List[CalendarTask]] = {}
        for task in tasks:
            date_key = task.date.strftime("%Y-%m-%d")
            if date_key not in tasks_by_date:
                tasks_by_date[date_key] = []
            tasks_by_date[date_key].append(task)

        scheduled = []

        for date_key in sorted(tasks_by_date.keys()):
            day_tasks = tasks_by_date[date_key]

            # Start at 9 AM
            current_time = datetime.strptime(date_key, "%Y-%m-%d").replace(hour=self.WORK_START_HOUR, minute=0)

            # Sort by project order (configured projects first, in order of configuration)
            # Build dynamic order from settings.all_projects
            project_order = {}
            for i, proj in enumerate(settings.all_projects):
                project_order[proj['name']] = i
            # Unknown projects sort last
            day_tasks.sort(key=lambda t: project_order.get(t.project, 99))

            for task in day_tasks:
                duration_minutes = int(task.duration_hours * 60)

                # Check if we need to skip lunch
                end_time = current_time + timedelta(minutes=duration_minutes)

                # If task starts before lunch and ends during lunch, move to after lunch
                if current_time.hour < self.LUNCH_START and end_time.hour >= self.LUNCH_START:
                    current_time = current_time.replace(hour=self.LUNCH_END, minute=0)

                # If currently in lunch break, move to after lunch
                if self.LUNCH_START <= current_time.hour < self.LUNCH_END:
                    current_time = current_time.replace(hour=self.LUNCH_END, minute=0)

                end_time = current_time + timedelta(minutes=duration_minutes)

                scheduled.append((task, current_time, end_time))

                # Add gap for next task
                current_time = end_time + timedelta(minutes=self.GAP_MINUTES)

        return scheduled

    def generate_ics(self, scheduled_tasks: List[Tuple[CalendarTask, datetime, datetime]]) -> str:
        """Generate ICS file content.

        Args:
            scheduled_tasks: List of (task, start_time, end_time) tuples

        Returns:
            ICS file content as string
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Build-in-Public//bip-daily-calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:BIP Daily Calendar",
            f"X-WR-TIMEZONE:{self.TIMEZONE}",
        ]

        # Add timezone definition
        lines.extend([
            "BEGIN:VTIMEZONE",
            f"TZID:{self.TIMEZONE}",
            "BEGIN:STANDARD",
            "DTSTART:19700101T000000",
            "TZOFFSETFROM:+0800",
            "TZOFFSETTO:+0800",
            "END:STANDARD",
            "END:VTIMEZONE",
        ])

        for task, start_time, end_time in scheduled_tasks:
            uid = str(uuid.uuid4())
            now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

            # Format times in local timezone
            dtstart = start_time.strftime("%Y%m%dT%H%M%S")
            dtend = end_time.strftime("%Y%m%dT%H%M%S")

            # Escape special characters in title
            summary = task.title.replace(",", "\\,").replace(";", "\\;").replace("\\", "\\\\")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART;TZID={self.TIMEZONE}:{dtstart}",
                f"DTEND;TZID={self.TIMEZONE}:{dtend}",
                f"SUMMARY:[{task.project}] {summary}",
                f"DESCRIPTION:Project: {task.project}\\nSource: {task.source_file}\\nDuration: {task.duration_hours}h",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ])

        lines.append("END:VCALENDAR")

        return "\r\n".join(lines)

    def generate_calendar(self) -> Path:
        """Main method to generate the calendar file.

        Returns:
            Path to the generated ICS file
        """
        print("📅 Generating BIP Daily Calendar...\n")

        # Find markdown files
        print(f"🔍 Searching for .md files in '{self.PLANS_DIR}/' directories...")
        files_by_project = self.find_markdown_files()

        if not files_by_project:
            print("\n⚠️  No matching files found in any project.")
            return None

        # Extract tasks from all files
        print("\n📝 Extracting tasks with dates...")
        all_tasks = []

        for project_name, files in files_by_project.items():
            for file_path in files:
                tasks = self.extract_tasks_from_file(file_path, project_name)
                if tasks:
                    print(f"  ✅ {file_path.name}: {len(tasks)} tasks with dates")
                    all_tasks.extend(tasks)

        if not all_tasks:
            print("\n⚠️  No tasks with dates found.")
            return None

        print(f"\n📊 Total tasks found: {len(all_tasks)}")

        # Schedule tasks
        print("\n⏰ Scheduling tasks (9 AM start, 20 min gaps, skip lunch 12-14)...")
        scheduled = self.schedule_tasks(all_tasks)

        # Generate ICS
        print("\n📄 Generating ICS file...")
        ics_content = self.generate_ics(scheduled)

        # Save to file
        output_file = self.output_dir / "bip-daily-calendar.ics"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(ics_content)

        print(f"\n✅ Calendar saved to: {output_file}")
        print(f"   Events: {len(scheduled)}")

        # Show preview
        if scheduled:
            print("\n📋 Preview (first 5 events):")
            for task, start, end in scheduled[:5]:
                print(f"   {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}: [{task.project}] {task.title[:40]}...")

        return output_file


if __name__ == "__main__":
    generator = CalendarGenerator()
    generator.generate_calendar()
