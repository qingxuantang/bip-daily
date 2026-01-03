"""Command-line interface for Build-in-Public system."""

import click
import time
import re
import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Confirm, IntPrompt
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from src.models import GeneratedPost, PostRecord, get_session, init_db, PostStatus
from src.collectors.aggregator import DataAggregator
from src.generators.post_generator import PostGenerator
from src.generators.calendar_generator import CalendarGenerator
from src.generators.temp_post_generator import TempPostGenerator
from src.generators.image_generator import ImageGenerator
from src.managers.meeting_manager import MeetingManager
from src.publishers.xiaohongshu import XiaohongshuPublisher
from src.publishers.twitter import TwitterPublisher
from src.config import settings
from pathlib import Path

console = Console()

# Daily-auto timing (from settings - can be overridden via .env)
# settings.daily_start_hour, settings.reschedule_hour loaded from settings

# SFTP configuration file path
SFTP_CONFIG_PATH = Path(__file__).parent.parent / "ftpinfo.json"

# Calendar file path (relative to project root for git operations)
CALENDAR_RELATIVE_PATH = "data/bip-daily-calendar.ics"


def _convert_windows_path_to_wsl(path: str) -> str:
    """Convert Windows path (D:/...) to WSL path (/mnt/d/...) if needed."""
    import platform
    # Check if running in WSL and path looks like Windows path
    if 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower():
        # Handle D:/ or D:\ style paths
        if len(path) >= 2 and path[1] == ':':
            drive_letter = path[0].lower()
            rest_of_path = path[2:].replace('\\', '/')
            return f"/mnt/{drive_letter}{rest_of_path}"
    return path


def upload_calendar_to_server(calendar_path: str) -> bool:
    """Upload the generated calendar file to the server via SFTP.

    Args:
        calendar_path: Path to the calendar .ics file to upload

    Returns:
        True if upload successful, False otherwise
    """
    try:
        import pysftp
    except ImportError:
        console.print("  [yellow]⚠️  pysftp not installed. Run: pip install pysftp[/yellow]")
        return False

    if not SFTP_CONFIG_PATH.exists():
        console.print(f"  [yellow]⚠️  SFTP config not found: {SFTP_CONFIG_PATH}[/yellow]")
        console.print("  [dim]Create ftpinfo.json with: host, user, private_key_path, passphrase, port[/dim]")
        return False

    try:
        with open(SFTP_CONFIG_PATH) as j:
            ftpinfo = json.load(j)

        host = ftpinfo['host']
        user = ftpinfo['user']
        private_key_path = ftpinfo['private_key_path']
        passphrase = ftpinfo['passphrase']
        port = ftpinfo.get('port', 22)

        # Convert Windows path to WSL path if needed
        private_key_path = _convert_windows_path_to_wsl(private_key_path)

        console.print(f"  [dim]Connecting to SFTP server...[/dim]")

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None  # Disable host key checking

        with pysftp.Connection(
            host,
            username=user,
            private_key=private_key_path,
            private_key_pass=passphrase,
            port=port,
            cnopts=cnopts
        ) as sftp:
            remote_folder = settings.sftp_remote_folder
            sftp.cwd(remote_folder)
            sftp.put(calendar_path)
            console.print(f"  [green]✅ Calendar uploaded to server: {remote_folder}/[/green]")

        return True

    except Exception as e:
        console.print(f"  [red]❌ SFTP upload failed: {e}[/red]")
        return False


def upload_calendar_to_github(calendar_path: str) -> bool:
    """Upload the calendar file to GitHub by committing and pushing.

    This enables automatic calendar updates for subscribers using the raw GitHub URL.
    Users can subscribe to: https://raw.githubusercontent.com/user/repo/main/data/bip-daily-calendar.ics

    Args:
        calendar_path: Path to the calendar .ics file to upload

    Returns:
        True if upload successful, False otherwise
    """
    import subprocess

    try:
        # Get the project root directory (where .git should be)
        project_root = Path(__file__).parent.parent

        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print("  [yellow]⚠️  Not a git repository. Skipping GitHub upload.[/yellow]")
            return False

        # Check if there are changes to the calendar file
        result = subprocess.run(
            ["git", "status", "--porcelain", CALENDAR_RELATIVE_PATH],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if not result.stdout.strip():
            console.print("  [dim]No changes to calendar file. Skipping commit.[/dim]")
            return True

        # Add the calendar file
        result = subprocess.run(
            ["git", "add", CALENDAR_RELATIVE_PATH],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print(f"  [red]❌ Git add failed: {result.stderr}[/red]")
            return False

        # Commit with a timestamp
        commit_msg = f"Update calendar: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            # Check if it's just "nothing to commit"
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                console.print("  [dim]No changes to commit.[/dim]")
                return True
            console.print(f"  [red]❌ Git commit failed: {result.stderr}[/red]")
            return False

        console.print(f"  [dim]Committed: {commit_msg}[/dim]")

        # Push to remote
        result = subprocess.run(
            ["git", "push"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print(f"  [yellow]⚠️  Git push failed: {result.stderr}[/yellow]")
            console.print("  [dim]Calendar committed locally. Push manually when ready.[/dim]")
            return False

        # Get remote URL for user reference
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip()
            # Convert SSH URL to HTTPS raw URL
            if remote_url.startswith("git@github.com:"):
                # git@github.com:user/repo.git -> https://raw.githubusercontent.com/user/repo/main/
                repo_path = remote_url.replace("git@github.com:", "").replace(".git", "")
                raw_url = f"https://raw.githubusercontent.com/{repo_path}/main/{CALENDAR_RELATIVE_PATH}"
            elif "github.com" in remote_url:
                # https://github.com/user/repo.git -> https://raw.githubusercontent.com/user/repo/main/
                repo_path = remote_url.replace("https://github.com/", "").replace(".git", "")
                raw_url = f"https://raw.githubusercontent.com/{repo_path}/main/{CALENDAR_RELATIVE_PATH}"
            else:
                raw_url = None

            console.print(f"  [green]✅ Calendar pushed to GitHub[/green]")
            if raw_url:
                console.print(f"  [dim]Subscribe URL: {raw_url}[/dim]")
        else:
            console.print(f"  [green]✅ Calendar pushed to GitHub[/green]")

        return True

    except FileNotFoundError:
        console.print("  [yellow]⚠️  Git not found. Skipping GitHub upload.[/yellow]")
        return False
    except Exception as e:
        console.print(f"  [red]❌ GitHub upload failed: {e}[/red]")
        return False


def upload_calendar_to_gist(calendar_path: str) -> bool:
    """Upload the calendar file to GitHub Gist for easy subscription.

    This is the recommended method for calendar sharing:
    - Works for any user (no fork/repo required)
    - Stable subscription URL
    - Auto-creates gist on first run, updates on subsequent runs

    Args:
        calendar_path: Path to the calendar .ics file to upload

    Returns:
        True if upload successful, False otherwise
    """
    import urllib.request
    import urllib.error

    if not settings.github_gist_token:
        console.print("  [yellow]⚠️  GITHUB_GIST_TOKEN not set in .env[/yellow]")
        console.print("  [dim]Create a token at: GitHub → Settings → Developer settings → Personal access tokens[/dim]")
        console.print("  [dim]Required scope: 'gist' only[/dim]")
        return False

    try:
        # Read calendar content
        with open(calendar_path, 'r', encoding='utf-8') as f:
            calendar_content = f.read()

        filename = "bip-daily-calendar.ics"
        gist_description = "BIP Calendar - Auto-updated task calendar"

        headers = {
            "Authorization": f"token {settings.github_gist_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "BIP-Calendar-Uploader"
        }

        # Load gist ID from env or data file
        gist_id = _load_gist_id()

        if gist_id:
            # Update existing gist
            url = f"https://api.github.com/gists/{gist_id}"
            data = json.dumps({
                "description": gist_description,
                "files": {
                    filename: {"content": calendar_content}
                }
            }).encode('utf-8')

            req = urllib.request.Request(url, data=data, headers=headers, method='PATCH')

            try:
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    raw_url = result['files'][filename]['raw_url']
                    # Remove the commit hash from URL for stable subscription
                    # https://gist.githubusercontent.com/user/id/raw/commit/file -> https://gist.githubusercontent.com/user/id/raw/file
                    parts = raw_url.split('/raw/')
                    if len(parts) == 2:
                        stable_url = f"{parts[0]}/raw/{filename}"
                    else:
                        stable_url = raw_url

                    console.print(f"  [green]✅ Calendar updated on GitHub Gist[/green]")
                    console.print(f"  [cyan]📅 Subscribe URL:[/cyan]")
                    console.print(f"  [bold cyan]{stable_url}[/bold cyan]")
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    console.print(f"  [yellow]⚠️  Gist {gist_id} not found. Creating new gist...[/yellow]")
                    # Clear the invalid gist ID and create new
                    gist_id = None
                else:
                    raise

        # Create new gist
        if not gist_id:
            url = "https://api.github.com/gists"
            data = json.dumps({
                "description": gist_description,
                "public": True,
                "files": {
                    filename: {"content": calendar_content}
                }
            }).encode('utf-8')

            req = urllib.request.Request(url, data=data, headers=headers, method='POST')

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                gist_id = result['id']
                raw_url = result['files'][filename]['raw_url']

                # Create stable URL without commit hash
                parts = raw_url.split('/raw/')
                if len(parts) == 2:
                    stable_url = f"{parts[0]}/raw/{filename}"
                else:
                    stable_url = raw_url

                console.print(f"  [green]✅ Calendar uploaded to new GitHub Gist[/green]")
                console.print(f"  [cyan]📅 Subscribe URL:[/cyan]")
                console.print(f"  [bold cyan]{stable_url}[/bold cyan]")
                # Save gist ID for future updates
                _save_gist_id(gist_id)

                return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        console.print(f"  [red]❌ GitHub API error ({e.code}): {error_body}[/red]")
        return False
    except Exception as e:
        console.print(f"  [red]❌ Gist upload failed: {e}[/red]")
        return False

    return False


def _save_gist_id(gist_id: str) -> None:
    """Save the gist ID to data directory and try to update .env file.

    In Docker, .env is not mounted as a volume, so we save to data/gist_id.txt
    which persists across container restarts. The gist ID is loaded from this
    file if GITHUB_GIST_ID is not set in environment.
    """
    project_root = Path(__file__).parent.parent

    # Always save to data directory (works in Docker since data/ is mounted)
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    gist_id_file = data_dir / "gist_id.txt"

    try:
        with open(gist_id_file, 'w', encoding='utf-8') as f:
            f.write(gist_id)
        console.print(f"  [dim]✅ Gist ID saved to data/gist_id.txt[/dim]")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Could not save gist ID to file: {e}[/yellow]")

    # Also try to update .env (works for local non-Docker usage)
    try:
        env_path = project_root / ".env"
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if GITHUB_GIST_ID already exists
            if 'GITHUB_GIST_ID=' in content:
                # Update existing line
                content = re.sub(
                    r'^GITHUB_GIST_ID=.*$',
                    f'GITHUB_GIST_ID={gist_id}',
                    content,
                    flags=re.MULTILINE
                )
            else:
                # Append new line
                if not content.endswith('\n'):
                    content += '\n'
                content += f'GITHUB_GIST_ID={gist_id}\n'

            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            console.print(f"  [dim]✅ GITHUB_GIST_ID also saved to .env[/dim]")
    except Exception:
        # Silent fail for .env - Docker users won't have write access
        pass


def _load_gist_id() -> Optional[str]:
    """Load gist ID from environment or data/gist_id.txt file."""
    # First check environment variable
    if settings.github_gist_id:
        return settings.github_gist_id

    # Then check data file (for Docker users)
    gist_id_file = Path(__file__).parent.parent / "data" / "gist_id.txt"
    if gist_id_file.exists():
        try:
            with open(gist_id_file, 'r', encoding='utf-8') as f:
                gist_id = f.read().strip()
                if gist_id:
                    return gist_id
        except Exception:
            pass

    return None


def upload_calendar(output_file, show_header: bool = True) -> None:
    """Upload calendar to configured destinations (Gist, GitHub repo, and/or SFTP).

    Args:
        output_file: Path to the calendar .ics file
        show_header: Whether to show upload header messages
    """
    # Upload to GitHub Gist (recommended, enabled by default)
    if settings.calendar_upload_gist:
        if show_header:
            console.print("\n[bold]📤 Uploading calendar to GitHub Gist...[/bold]")
        upload_calendar_to_gist(str(output_file))

    # Upload to GitHub repo (disabled by default, requires fork or own repo)
    if settings.calendar_upload_github:
        if show_header:
            console.print("\n[bold]📤 Uploading calendar to GitHub repo...[/bold]")
        upload_calendar_to_github(str(output_file))

    # Upload to SFTP server (disabled by default)
    if settings.calendar_upload_sftp:
        if show_header:
            console.print("\n[bold]📤 Uploading calendar to SFTP server...[/bold]")
        upload_calendar_to_server(str(output_file))


@click.group()
def cli():
    """Build-in-Public Daily Posting System."""
    pass


@cli.command()
def init():
    """Initialize the system (database, config)."""
    console.print("[bold green]🚀 Initializing Build-in-Public system...[/bold green]")

    # Initialize database
    init_db()
    console.print("   ✅ Database initialized")

    # Check configuration
    if not settings.anthropic_api_key and not settings.openai_api_key:
        console.print("   ⚠️  [yellow]No AI API key configured![/yellow]")
        console.print("      Please set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")

    console.print("\n[bold]✨ Initialization complete![/bold]")
    console.print(f"   Projects monitored: {len(settings.projects)}")
    console.print(f"   Posts per day: {settings.posts_per_day}")


def _extract_image_prompts_from_content(content: str) -> tuple:
    """Extract Image Prompts section from content.

    Args:
        content: Post content that may contain Image Prompts section

    Returns:
        Tuple of (content_without_prompts, image_prompts_section)
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


def save_post_to_markdown(post: PostRecord, output_dir: str = "data/selected_posts") -> Path:
    """Save a selected post to a markdown file for manual publishing.

    Extracts Image Prompts section and saves to separate file.

    Args:
        post: PostRecord to save
        output_dir: Directory to save the markdown file

    Returns:
        Path to the saved markdown file
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp and post ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"post_{timestamp}_id{post.id}"
    filename = f"{base_filename}.md"
    filepath = output_path / filename

    # Extract image prompts from post content
    post_content, image_prompts = _extract_image_prompts_from_content(post.content)

    # Prepare markdown content with metadata (without image prompts)
    markdown_content = f"""# {post.style.upper()} - Build in Public Post

**Post ID:** {post.id}
**Generated:** {post.created_at.strftime("%Y-%m-%d %H:%M:%S")}
**Word Count:** {post.word_count}
**Status:** {post.status}

---

## Hashtags

{' '.join(['#' + tag for tag in post.hashtags])}

---

## Content

{post_content}

---

## Metadata

- **Projects Mentioned:** {', '.join(post.projects_mentioned) if post.projects_mentioned else 'None'}
- **Technical Keywords:** {', '.join(post.technical_keywords[:10]) if post.technical_keywords else 'None'}
- **Selected At:** {post.selected_at.strftime("%Y-%m-%d %H:%M:%S") if post.selected_at else 'N/A'}

---

*Ready for manual publishing to Xiaohongshu*
"""

    # Write post to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    # Save image prompts to separate file if extracted
    if image_prompts:
        image_prompt_filename = f"image-prompt_{base_filename}.md"
        image_prompt_filepath = output_path / image_prompt_filename
        image_prompt_content = f"""# Image Generation Prompts - Post {post.id}

**Generated at:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**For use with:** Gemini Imagen 3 API
**Associated post:** {filename}

---

{image_prompts}
"""
        with open(image_prompt_filepath, 'w', encoding='utf-8') as f:
            f.write(image_prompt_content)
        console.print(f"    🎨 Image prompts saved to: {image_prompt_filepath}")
    else:
        console.print(f"    ⚠️  No image prompts found in post content")

    return filepath


@cli.command()
@click.option('--days', default=None, type=int, help='Days to look back')
def collect(days):
    """Collect data from all sources."""
    lookback = days or settings.lookback_days

    console.print(f"[bold]📦 Collecting data from past {lookback} days...[/bold]\n")

    aggregator = DataAggregator(lookback_days=lookback)
    data = aggregator.collect_all_data()
    highlights = aggregator.get_highlights(data)

    # Display summary
    table = Table(title="Collection Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Git Commits", str(highlights['total_commits']))
    table.add_row("Active Projects", str(highlights['active_projects']))
    table.add_row("Claude Sessions", str(highlights['total_sessions']))
    table.add_row("Topics", str(len(highlights['all_topics'])))

    console.print(table)

    if highlights['major_updates']:
        console.print("\n[bold]🔥 Major Updates:[/bold]")
        for update in highlights['major_updates']:
            console.print(f"   • {update['project']}: {update['commits']} commits")


@cli.command()
@click.option('--count', default=None, type=int, help='Number of posts to generate')
@click.option('--days', default=None, type=int, help='Days to look back')
def generate(count, days):
    """Generate posts for today."""
    post_count = count or settings.posts_per_day
    lookback = days or settings.lookback_days

    console.print(f"[bold]✨ Generating {post_count} posts...[/bold]\n")

    # Collect data
    aggregator = DataAggregator(lookback_days=lookback)
    data = aggregator.collect_all_data()

    # Generate posts
    generator = PostGenerator()
    posts = generator.generate_multiple_posts(data, count=post_count)

    # Save to database
    session = get_session()
    saved_posts = []

    for i, post in enumerate(posts, 1):
        record = PostRecord(
            generation_date=datetime.now(),
            content=post.content,
            style=post.style.value,
            language=post.language.value,
            hashtags=post.hashtags,
            word_count=post.word_count,
            projects_mentioned=post.projects_mentioned,
            technical_keywords=post.technical_keywords,
            source_data=data.model_dump(mode='json'),
            generation_metadata=post.metadata,
            status=PostStatus.DRAFT.value,
        )
        session.add(record)
        saved_posts.append(record)

    session.commit()

    console.print(f"[bold green]✅ Generated and saved {len(posts)} posts to database![/bold green]")

    # Auto-save ALL posts to selected_posts directory
    console.print(f"\n[bold]📁 Auto-saving all {len(saved_posts)} posts to selected_posts/...[/bold]")
    for record in saved_posts:
        try:
            filepath = save_post_to_markdown(record)
            console.print(f"   ✅ Saved: {filepath.name}")
        except Exception as e:
            console.print(f"   [yellow]⚠️  Failed to save post #{record.id}: {e}[/yellow]")

    console.print(f"\n   Use 'python -m src.cli select' to choose which one to post\n")


@cli.command()
def select():
    """Select a post to publish."""
    session = get_session()

    # Get today's draft posts
    today = datetime.now().date()
    posts = session.query(PostRecord).filter(
        PostRecord.status == PostStatus.DRAFT.value,
    ).order_by(PostRecord.created_at.desc()).limit(10).all()

    if not posts:
        console.print("[yellow]⚠️  No draft posts found. Generate some first![/yellow]")
        console.print("   Run: python -m src.cli generate")
        return

    console.print("[bold]📋 Available Posts:[/bold]\n")

    # Display posts
    for i, post in enumerate(posts, 1):
        # Add language flag
        lang_flag = "🇨🇳" if post.language == "zh" else "🇬🇧"
        lang_name = "Chinese" if post.language == "zh" else "English"

        console.print(Panel(
            Markdown(post.content),
            title=f"Post {i} {lang_flag} - {post.style} ({post.word_count} words)",
            subtitle=f"ID: {post.id} | Language: {lang_name} | {', '.join(post.hashtags[:3])}...",
            border_style="cyan" if i % 2 == 0 else "blue"
        ))
        console.print()

    # Ask user to select
    choice = IntPrompt.ask(
        f"Select a post to publish (1-{len(posts)}) or 0 to cancel",
        default=1
    )

    if choice == 0:
        console.print("[yellow]❌ Cancelled[/yellow]")
        return

    if choice < 1 or choice > len(posts):
        console.print("[red]❌ Invalid choice[/red]")
        return

    selected_post = posts[choice - 1]

    # Confirm selection
    if not Confirm.ask(f"✅ Publish Post {choice}?"):
        console.print("[yellow]❌ Cancelled[/yellow]")
        return

    # Update status
    selected_post.status = PostStatus.SELECTED.value
    selected_post.selected_at = datetime.now()

    # Reject other posts from same generation
    for post in posts:
        if post.id != selected_post.id and post.status == PostStatus.DRAFT.value:
            post.status = PostStatus.REJECTED.value

    session.commit()

    console.print(f"[bold green]✅ Post {choice} selected![/bold green]")

    # Save to markdown file for manual publishing
    try:
        filepath = save_post_to_markdown(selected_post)
        console.print(f"\n[bold cyan]📝 Post saved to markdown file:[/bold cyan]")
        console.print(f"   {filepath}")
        console.print(f"\n[bold]You can now manually copy and publish the content to Xiaohongshu[/bold]")
    except Exception as e:
        console.print(f"[red]❌ Failed to save markdown file: {e}[/red]")


@cli.command()
@click.argument('post_id', type=int)
def publish(post_id):
    """Publish a selected post to Xiaohongshu."""
    publish_post(post_id)


@cli.command()
@click.argument('post_id', type=int)
def publish_twitter(post_id):
    """Publish a selected post to X.com (Twitter)."""
    publish_to_twitter(post_id)


@cli.command()
@click.argument('post_id', type=int)
def publish_both(post_id):
    """Publish a selected post to both Xiaohongshu and X.com (Twitter)."""
    console.print(f"[bold]📤 Publishing to both platforms...[/bold]\n")

    # Publish to Xiaohongshu
    console.print("[bold cyan]Publishing to Xiaohongshu...[/bold cyan]")
    publish_post(post_id)

    # Publish to Twitter
    console.print("\n[bold cyan]Publishing to X.com (Twitter)...[/bold cyan]")
    publish_to_twitter(post_id)

    console.print(f"\n[bold green]✅ Published to both platforms![/bold green]")


def publish_post(post_id: int):
    """Publish a post to Xiaohongshu.

    Args:
        post_id: Post database ID
    """
    session = get_session()
    post = session.query(PostRecord).filter_by(id=post_id).first()

    if not post:
        console.print(f"[red]❌ Post {post_id} not found[/red]")
        return

    if post.status == PostStatus.PUBLISHED.value:
        console.print(f"[yellow]⚠️  Post already published![/yellow]")
        console.print(f"   URL: {post.xhs_url}")
        return

    console.print(f"[bold]📤 Publishing to Xiaohongshu...[/bold]\n")

    try:
        publisher = XiaohongshuPublisher()
        result = publisher.publish(
            content=post.content,
            title=post.content.split('\n')[0][:50],  # First line as title
        )

        # Update post record
        post.status = PostStatus.PUBLISHED.value
        post.published_at = datetime.now()
        post.xhs_post_id = result.get('post_id')
        post.xhs_url = result.get('url')

        session.commit()

        console.print(f"[bold green]✅ Published successfully![/bold green]")
        if result.get('url'):
            console.print(f"   URL: {result['url']}")

    except Exception as e:
        console.print(f"[red]❌ Publishing failed: {e}[/red]")
        console.print("   Please check your Xiaohongshu credentials")


def publish_to_twitter(post_id: int):
    """Publish a post to X.com (Twitter).

    Args:
        post_id: Post database ID
    """
    session = get_session()
    post = session.query(PostRecord).filter_by(id=post_id).first()

    if not post:
        console.print(f"[red]❌ Post {post_id} not found[/red]")
        return

    if post.twitter_url:
        console.print(f"[yellow]⚠️  Post already published to Twitter![/yellow]")
        console.print(f"   URL: {post.twitter_url}")
        return

    console.print(f"[bold]📤 Publishing to X.com (Twitter)...[/bold]\n")

    try:
        # Check if Twitter credentials are configured
        if not settings.twitter_username or not settings.twitter_password:
            console.print(f"[yellow]⚠️  Twitter credentials not configured in .env[/yellow]")
            console.print("   Please set TWITTER_USERNAME and TWITTER_PASSWORD")
            return

        publisher = TwitterPublisher()
        result = publisher.publish(
            content=post.content,
        )

        # Update post record
        post.twitter_post_id = result.get('post_id')
        post.twitter_url = result.get('url')
        post.twitter_published_at = datetime.now()

        session.commit()

        console.print(f"[bold green]✅ Published to Twitter successfully![/bold green]")
        if result.get('url'):
            console.print(f"   URL: {result['url']}")

    except Exception as e:
        console.print(f"[red]❌ Publishing failed: {e}[/red]")
        console.print("   Please check your Twitter credentials")


@cli.command()
@click.option('--limit', default=10, type=int, help='Number of posts to show')
def history(limit):
    """View post history."""
    session = get_session()
    posts = session.query(PostRecord).order_by(
        PostRecord.created_at.desc()
    ).limit(limit).all()

    if not posts:
        console.print("[yellow]No posts found[/yellow]")
        return

    table = Table(title=f"Post History (Last {len(posts)})")
    table.add_column("ID", style="cyan")
    table.add_column("Lang", style="magenta")
    table.add_column("Date", style="green")
    table.add_column("Style", style="blue")
    table.add_column("Words", justify="right")
    table.add_column("Status", style="yellow")
    table.add_column("Published")

    for post in posts:
        lang_flag = "🇨🇳" if post.language == "zh" else "🇬🇧"
        table.add_row(
            str(post.id),
            lang_flag,
            post.created_at.strftime("%Y-%m-%d %H:%M"),
            post.style,
            str(post.word_count),
            post.status,
            post.published_at.strftime("%Y-%m-%d") if post.published_at else "-",
        )

    console.print(table)


@cli.command()
@click.argument('post_id', type=int)
def view(post_id):
    """View a specific post."""
    session = get_session()
    post = session.query(PostRecord).filter_by(id=post_id).first()

    if not post:
        console.print(f"[red]Post {post_id} not found[/red]")
        return

    lang_flag = "🇨🇳" if post.language == "zh" else "🇬🇧"
    lang_name = "Chinese" if post.language == "zh" else "English"

    console.print(Panel(
        Markdown(post.content),
        title=f"Post #{post.id} {lang_flag} - {post.style}",
        subtitle=f"Language: {lang_name} | Status: {post.status} | {post.word_count} words | {post.created_at.strftime('%Y-%m-%d %H:%M')}",
        border_style="cyan"
    ))

    # Show metadata
    console.print(f"\n[bold]Metadata:[/bold]")
    console.print(f"  Hashtags: {', '.join(post.hashtags)}")
    console.print(f"  Projects: {', '.join(post.projects_mentioned)}")
    console.print(f"  Keywords: {', '.join(post.technical_keywords[:10])}")

    if post.xhs_url:
        console.print(f"\n[bold]Xiaohongshu:[/bold]")
        console.print(f"  URL: {post.xhs_url}")
        console.print(f"  Published: {post.published_at.strftime('%Y-%m-%d %H:%M')}")

    if post.twitter_url:
        console.print(f"\n[bold]X.com (Twitter):[/bold]")
        console.print(f"  URL: {post.twitter_url}")
        console.print(f"  Published: {post.twitter_published_at.strftime('%Y-%m-%d %H:%M') if post.twitter_published_at else 'N/A'}")


@cli.command()
def calendar():
    """Generate ICS calendar from project todos with dates."""
    console.print("[bold]📅 Generating BIP Daily Calendar...[/bold]\n")

    try:
        generator = CalendarGenerator()
        output_file = generator.generate_calendar()

        if output_file:
            console.print(f"\n[bold green]✅ Calendar generated successfully![/bold green]")
            console.print(f"   File: {output_file}")

            # Upload to configured destinations
            upload_calendar(output_file)

            console.print(f"\n[bold]Import this file into your calendar app (Google Calendar, Apple Calendar, Outlook, etc.)[/bold]")
        else:
            console.print("[yellow]⚠️  No tasks with dates found in project todos.[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Calendar generation failed: {e}[/red]")


@cli.command()
def reschedule():
    """Run the reschedule procedure: find undone tasks and regenerate calendar.

    This command runs the 23:00 PM reschedule procedure manually:
    1. Scans all project launch plans for undone tasks from past 3 days
    2. Intelligently reschedules them based on time budget constraints
    3. Marks overdue tasks with [moved to Date] in the checkbox
    4. Regenerates and uploads the calendar to the server

    IMPORTANT: This procedure NEVER removes any tasks - all history is preserved.

    Usage: ./bip reschedule
    """
    console.print("[bold]📋 Running Manual Reschedule Procedure...[/bold]\n")

    try:
        undone_count, cal_path = run_reschedule_procedure()

        if undone_count == 0:
            console.print("\n[green]✅ No undone tasks to reschedule![/green]")
        else:
            console.print(f"\n[green]✅ Rescheduled {undone_count} task(s)[/green]")

        if cal_path:
            console.print(f"[green]📅 Calendar updated: {cal_path}[/green]")

    except Exception as e:
        console.print(f"[red]❌ Reschedule failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@cli.command('temp-post')
def temp_post():
    """Process new folders in data/temp_posts and generate posts.

    This command scans the data/temp_posts directory for folders that
    don't have a post.ready marker file, generates posts from their
    content using style references, and marks them as processed.

    A folder is considered "new" if it doesn't contain a post.ready file.
    After processing, the command creates:
    - post.md: The generated post content
    - post.ready: Marker indicating the folder has been processed
    """
    console.print("[bold]📝 Processing Temp Posts...[/bold]\n")

    try:
        generator = TempPostGenerator()
        processed, failed = generator.process_all_unprocessed()

        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"   Processed: {processed}")
        console.print(f"   Failed: {failed}")

        if processed > 0:
            console.print(f"\n[bold green]✅ Temp post processing complete![/bold green]")
        elif failed > 0:
            console.print(f"\n[yellow]⚠️  Some folders failed to process[/yellow]")
        else:
            console.print(f"\n[cyan]ℹ️  No new folders to process[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Temp post processing failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


def run_temp_post_check() -> Tuple[int, int]:
    """Run temp post check (for use in daily-auto).

    Returns:
        Tuple of (processed_count, failed_count)
    """
    try:
        generator = TempPostGenerator()
        return generator.process_all_unprocessed()
    except Exception as e:
        console.print(f"[red]❌ Temp post check failed: {e}[/red]")
        return 0, 0


def save_temp_post_to_db(folder_path: Path) -> Optional[PostRecord]:
    """Save a temp post to database for scheduling.

    Args:
        folder_path: Path to the temp post folder

    Returns:
        PostRecord if successful, None otherwise
    """
    # Find post.md file
    post_file = folder_path / "post.md"
    if not post_file.exists():
        # Try alternative filename
        post_file = folder_path / "post_链接内容无法获取.md"
        if not post_file.exists():
            console.print(f"  [yellow]⚠️  No post.md found in {folder_path.name}[/yellow]")
            return None

    try:
        with open(post_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract actual post content (skip metadata header)
        # File format: metadata header, ---, content (may have multiple --- separators), ---
        if "---" in content:
            parts = content.split("---")
            if len(parts) >= 2:
                # Skip first part (metadata), join the rest with ---
                main_parts = parts[1:]
                content = "---".join(main_parts).strip()
                # Remove trailing --- if present
                if content.endswith("---"):
                    content = content[:-3].strip()

        # Remove Image Prompts section if present
        post_content, _ = _extract_image_prompts_from_content(content)

        # Create PostRecord
        session = get_session()
        post = PostRecord(
            content=post_content,
            style="temp_post",
            language="zh",
            generation_date=datetime.now(),
            status=PostStatus.DRAFT.value,
            generation_metadata={
                "folder_path": str(folder_path),
                "folder_name": folder_path.name,
                "source": "temp_post"
            }
        )
        session.add(post)
        session.commit()

        console.print(f"  [green]✅ Saved temp post to database: #{post.id}[/green]")
        return post

    except Exception as e:
        console.print(f"  [red]❌ Failed to save temp post: {e}[/red]")
        return None


def schedule_temp_post(folder_name: str, platforms: List[str] = None) -> bool:
    """Schedule a temp post for publishing.

    Args:
        folder_name: Name of the folder in data/temp_posts/
        platforms: List of platforms to publish to (default: twitter only)

    Returns:
        True if scheduled successfully
    """
    from src.schedulers.post_scheduler import PostScheduler

    temp_posts_dir = Path(settings.base_dir) / "data" / "temp_posts"
    folder_path = temp_posts_dir / folder_name

    if not folder_path.exists():
        console.print(f"[red]❌ Folder not found: {folder_name}[/red]")
        return False

    # Save to database
    post = save_temp_post_to_db(folder_path)
    if not post:
        return False

    # Schedule the post using the scheduler's session
    scheduler = PostScheduler()

    # Re-query the post using the scheduler's session to avoid session conflicts
    post = scheduler.session.query(PostRecord).filter(PostRecord.id == post.id).first()
    if not post:
        console.print(f"  [red]❌ Failed to find post in database[/red]")
        return False

    scheduled_time = scheduler.schedule_post(
        post,
        platforms=platforms,
        source="temp_post"
    )

    if scheduled_time:
        console.print(f"  [green]✅ Scheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M')}[/green]")
        return True
    else:
        console.print(f"  [red]❌ Failed to find available slot[/red]")
        return False


def list_temp_posts_for_scheduling() -> List[dict]:
    """List temp posts that are ready but not yet scheduled.

    Returns:
        List of dicts with folder info
    """
    temp_posts_dir = Path(settings.base_dir) / "data" / "temp_posts"
    posts = []

    if not temp_posts_dir.exists():
        return posts

    for folder in temp_posts_dir.iterdir():
        if not folder.is_dir():
            continue

        # Check if has post.ready (processed)
        ready_file = folder / "post.ready"
        if not ready_file.exists():
            continue

        # Check if already published (has publish.ready marker)
        publish_ready = folder / "publish.ready"
        if publish_ready.exists():
            continue  # Skip already published posts

        # Check if has post.md
        post_file = folder / "post.md"
        if not post_file.exists():
            post_file = folder / "post_链接内容无法获取.md"
            if not post_file.exists():
                continue

        # Check if already in database
        session = get_session()
        existing = session.query(PostRecord).filter(
            PostRecord.generation_metadata.contains(folder.name)
        ).first()

        posts.append({
            "folder_name": folder.name,
            "folder_path": folder,
            "has_images": (folder / "images.ready").exists(),
            "already_scheduled": existing is not None,
            "post_id": existing.id if existing else None
        })

    return posts


@cli.command('generate-images')
@click.option('--platform', default='xiaohongshu',
              type=click.Choice(['xiaohongshu', 'twitter', 'instagram', 'linkedin']),
              help='Target platform for image dimensions')
@click.option('--force', is_flag=True, help='Force regeneration of existing images')
def generate_images(platform: str, force: bool):
    """Generate images for all posts that have been created but don't have images yet.

    This command scans both temp_posts and selected_posts directories:
    - temp_posts: Processes folders that have post.ready but not images.ready
    - selected_posts: Creates images in data/post-images/

    The generated images are saved in an 'images' subfolder with:
    - images/cover.png (and other named images if multiple prompts exist)
    - images.ready marker file when complete

    Image generation uses Gemini Imagen 3 API with automatic fallback to Gemini Flash.

    Usage:
        ./bip generate-images                    # Default: xiaohongshu dimensions
        ./bip generate-images --platform twitter # Twitter 16:9 dimensions
        ./bip generate-images --force            # Regenerate all images
    """
    console.print("[bold]🎨 Generating Post Images...[/bold]\n")

    try:
        generator = ImageGenerator()
        processed, failed, skipped = generator.process_unprocessed_posts(
            platform=platform,
            force=force
        )

        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"   Processed: {processed}")
        console.print(f"   Failed: {failed}")
        console.print(f"   Skipped: {skipped}")

        if processed > 0:
            console.print(f"\n[bold green]✅ Image generation complete![/bold green]")
        elif failed > 0:
            console.print(f"\n[yellow]⚠️  Some image generations failed[/yellow]")
        else:
            console.print(f"\n[cyan]ℹ️  No new images to generate[/cyan]")

    except Exception as e:
        console.print(f"[red]❌ Image generation failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


def run_image_generation(platform: str = "xiaohongshu") -> Tuple[int, int, int]:
    """Run image generation (for use in daily-auto).

    Args:
        platform: Target platform for image dimensions

    Returns:
        Tuple of (processed_count, failed_count, skipped_count)
    """
    try:
        generator = ImageGenerator()
        return generator.process_unprocessed_posts(platform=platform)
    except Exception as e:
        console.print(f"[red]❌ Image generation failed: {e}[/red]")
        return 0, 0, 0


def auto_schedule_temp_posts(platforms: List[str] = None) -> Tuple[int, int]:
    """Auto-schedule temp posts that have images but are not yet scheduled.

    Args:
        platforms: List of platforms to schedule for (default: twitter only)

    Returns:
        Tuple of (scheduled_count, failed_count)
    """
    if platforms is None:
        platforms = ["twitter"]

    scheduled_count = 0
    failed_count = 0

    try:
        # Get all temp posts ready for scheduling
        posts = list_temp_posts_for_scheduling()

        # Filter for posts that have images but are not yet scheduled
        schedulable = [p for p in posts if p["has_images"] and not p["already_scheduled"]]

        if not schedulable:
            return 0, 0

        console.print(f"\n[bold]📅 Auto-scheduling {len(schedulable)} temp post(s)...[/bold]")

        for post_info in schedulable:
            folder_name = post_info["folder_name"]
            console.print(f"  📝 Scheduling: {folder_name}")

            success = schedule_temp_post(folder_name, platforms)
            if success:
                scheduled_count += 1
            else:
                failed_count += 1

    except Exception as e:
        console.print(f"[red]❌ Auto-scheduling failed: {e}[/red]")

    return scheduled_count, failed_count


def check_today_meeting_exists() -> Optional[Path]:
    """Check if today's meeting file has already been generated.

    Returns:
        Path to existing meeting file if found, None otherwise
    """
    meetings_dir = Path(settings.base_dir) / "data" / "meetings"
    if not meetings_dir.exists():
        return None

    today_str = datetime.now().strftime('%Y%m%d')
    pattern = f"meeting_{today_str}_*.md"

    # Find any meeting file from today
    existing_files = list(meetings_dir.glob(pattern))
    if existing_files:
        # Return the most recent one
        return max(existing_files, key=lambda f: f.stat().st_mtime)
    return None


@cli.command()
@click.option('--save/--no-save', default=True, help='Save report to file')
def meeting(save):
    """Run morning meeting - review yesterday, plan today, track weekly goals.

    This command coordinates all AI agents by:
    1. Reviewing yesterday's accomplishments (git commits from all projects)
    2. Extracting today's tasks from launch plans
    3. Tracking weekly goals
    4. Showing AI workflow references
    5. Displaying agent assignments

    Usage: ./bip meeting
    """
    console.print("[bold]🌅 Starting Morning Meeting...[/bold]\n")

    try:
        manager = MeetingManager()
        report, text, filepath = manager.run_meeting()

        # Display the report
        console.print(Markdown(text))

        console.print(f"\n[bold green]✅ Meeting report saved to:[/bold green]")
        console.print(f"   {filepath}")

        # Summary stats
        total_commits = sum(len(p.yesterday_commits) for p in report.projects)
        total_tasks = sum(len(p.today_tasks) for p in report.projects)
        blocked_projects = [p.name for p in report.projects if "Blocked" in p.health]

        console.print(f"\n[bold]📊 Summary:[/bold]")
        console.print(f"   Yesterday's commits: {total_commits}")
        console.print(f"   Today's tasks: {total_tasks}")
        if blocked_projects:
            console.print(f"   [red]⚠️  Blocked projects: {', '.join(blocked_projects)}[/red]")
        else:
            console.print(f"   [green]✅ All projects on track[/green]")

    except Exception as e:
        console.print(f"[red]❌ Meeting failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@cli.command()
def daily():
    """Run daily workflow: collect → generate → select → publish."""
    console.print("[bold]🌅 Running daily Build-in-Public workflow...[/bold]\n")

    # Step 1: Collect data
    console.print("[bold cyan]📦 Step 1: Collecting data...[/bold cyan]")
    aggregator = DataAggregator()
    data = aggregator.collect_all_data()
    highlights = aggregator.get_highlights(data)

    if highlights['total_commits'] == 0:
        console.print("[yellow]⚠️  No activity found. Skipping post generation.[/yellow]")
        return

    # Step 2: Generate posts
    console.print(f"\n[bold cyan]✨ Step 2: Generating {settings.posts_per_day} posts...[/bold cyan]")
    generator = PostGenerator()
    posts = generator.generate_multiple_posts(data, count=settings.posts_per_day)

    # Save posts
    session = get_session()
    saved_posts = []
    for post in posts:
        record = PostRecord(
            generation_date=datetime.now(),
            content=post.content,
            style=post.style.value,
            language=post.language.value,
            hashtags=post.hashtags,
            word_count=post.word_count,
            projects_mentioned=post.projects_mentioned,
            technical_keywords=post.technical_keywords,
            source_data=data.model_dump(mode='json'),
            generation_metadata=post.metadata,
            status=PostStatus.DRAFT.value,
        )
        session.add(record)
        saved_posts.append(record)
    session.commit()

    console.print(f"   ✅ Generated {len(posts)} posts")

    # Step 3: User selects post (manual)
    console.print(f"\n[bold cyan]👆 Step 3: Select post to publish[/bold cyan]")
    console.print("   Run: python -m src.cli select")

    console.print(f"\n[bold green]✨ Daily workflow complete![/bold green]")


def wait_until_time(target_hour: int, target_minute: int = 0) -> bool:
    """Wait until a specific time of day.

    Args:
        target_hour: Target hour (0-23)
        target_minute: Target minute (0-59)

    Returns:
        True if waited successfully, False if target time has already passed
    """
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

    # If target time has already passed today, return False
    if now >= target:
        return False

    # Calculate seconds to wait
    wait_seconds = (target - now).total_seconds()

    console.print(f"\n[bold yellow]⏰ Waiting until {target_hour:02d}:{target_minute:02d}...[/bold yellow]")
    console.print(f"   Current time: {now.strftime('%H:%M:%S')}")
    console.print(f"   Wait time: {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m")

    # Show countdown every 10 minutes
    while datetime.now() < target:
        remaining = (target - datetime.now()).total_seconds()
        if remaining > 0:
            # Sleep in 60-second intervals for responsiveness
            sleep_time = min(60, remaining)
            time.sleep(sleep_time)

            # Show status every 10 minutes
            remaining_after = (target - datetime.now()).total_seconds()
            if int(remaining // 600) != int(remaining_after // 600):  # Every 10 min
                console.print(f"   ⏳ {int(remaining_after // 60)} minutes remaining...")

    console.print(f"   [green]✅ Target time reached: {datetime.now().strftime('%H:%M:%S')}[/green]")
    return True


def auto_select_post() -> Optional[PostRecord]:
    """Automatically select the first available Chinese draft post.

    Returns:
        Selected PostRecord or None if no posts available
    """
    session = get_session()

    # Get recent draft posts, prefer Chinese
    posts = session.query(PostRecord).filter(
        PostRecord.status == PostStatus.DRAFT.value,
    ).order_by(PostRecord.created_at.desc()).limit(10).all()

    if not posts:
        console.print("[yellow]⚠️  No draft posts found for auto-select[/yellow]")
        return None

    # Prefer Chinese post
    chinese_posts = [p for p in posts if p.language == "zh"]
    selected_post = chinese_posts[0] if chinese_posts else posts[0]

    # Update status
    selected_post.status = PostStatus.SELECTED.value
    selected_post.selected_at = datetime.now()

    # Reject other posts from same generation
    for post in posts:
        if post.id != selected_post.id and post.status == PostStatus.DRAFT.value:
            post.status = PostStatus.REJECTED.value

    session.commit()

    lang_flag = "🇨🇳" if selected_post.language == "zh" else "🇬🇧"
    console.print(f"[bold green]✅ Auto-selected post #{selected_post.id} {lang_flag}[/bold green]")

    # Save to markdown file
    try:
        filepath = save_post_to_markdown(selected_post)
        console.print(f"   📝 Saved to: {filepath}")
    except Exception as e:
        console.print(f"[yellow]⚠️  Failed to save markdown: {e}[/yellow]")

    return selected_post


def auto_publish_post(post: PostRecord) -> bool:
    """Automatically publish a post to Xiaohongshu.

    Args:
        post: PostRecord to publish

    Returns:
        True if published successfully
    """
    if not post:
        return False

    console.print(f"\n[bold]📤 Auto-publishing post #{post.id} to Xiaohongshu...[/bold]")

    try:
        from src.publishers.xiaohongshu import XiaohongshuPublisher

        publisher = XiaohongshuPublisher()
        result = publisher.publish(
            content=post.content,
            title=post.content.split('\n')[0][:50],
        )

        # Update post record
        session = get_session()
        post.status = PostStatus.PUBLISHED.value
        post.published_at = datetime.now()
        post.xhs_post_id = result.get('post_id')
        post.xhs_url = result.get('url')
        session.commit()

        console.print(f"[bold green]✅ Published successfully![/bold green]")
        if result.get('url'):
            console.print(f"   URL: {result['url']}")
        return True

    except Exception as e:
        console.print(f"[red]❌ Auto-publish failed: {e}[/red]")
        return False


def wait_until_time_with_hourly_check(target_hour: int, target_minute: int = 0) -> bool:
    """Wait until a specific time while running hourly temp-post checks.

    Args:
        target_hour: Target hour (0-23)
        target_minute: Target minute (0-59)

    Returns:
        True if waited successfully, False if target time has already passed
    """
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

    # If target time has already passed today, return False
    if now >= target:
        return False

    # Calculate seconds to wait
    wait_seconds = (target - now).total_seconds()

    console.print(f"\n[bold yellow]⏰ Waiting until {target_hour:02d}:{target_minute:02d}...[/bold yellow]")
    console.print(f"   Current time: {now.strftime('%H:%M:%S')}")
    console.print(f"   Wait time: {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m")
    console.print(f"   [cyan]📝 Will check for new temp posts + generate images every hour[/cyan]")

    last_check_hour = now.hour
    temp_post_total_processed = 0
    temp_post_total_failed = 0
    img_total_processed = 0
    img_total_failed = 0

    # Show countdown and check hourly
    while datetime.now() < target:
        current_time = datetime.now()
        remaining = (target - current_time).total_seconds()

        if remaining <= 0:
            break

        # Check for new temp posts every hour
        if current_time.hour != last_check_hour:
            console.print(f"\n[cyan]🔄 Hourly temp-post check ({current_time.strftime('%H:%M')})...[/cyan]")
            processed, failed = run_temp_post_check()
            temp_post_total_processed += processed
            temp_post_total_failed += failed
            if processed > 0:
                console.print(f"   [green]✅ Processed {processed} new temp post(s)[/green]")

                # Generate images for newly processed posts
                console.print(f"   [cyan]🎨 Generating images for new posts...[/cyan]")
                img_proc, img_fail, _ = run_image_generation()
                img_total_processed += img_proc
                img_total_failed += img_fail
                if img_proc > 0:
                    console.print(f"   [green]✅ Generated images for {img_proc} post(s)[/green]")
            else:
                console.print(f"   [dim]No new temp posts[/dim]")
            last_check_hour = current_time.hour

        # Sleep in 60-second intervals for responsiveness
        sleep_time = min(60, remaining)
        time.sleep(sleep_time)

        # Show status every 10 minutes
        remaining_after = (target - datetime.now()).total_seconds()
        if int(remaining // 600) != int(remaining_after // 600):  # Every 10 min
            console.print(f"   ⏳ {int(remaining_after // 60)} minutes remaining...")

    console.print(f"   [green]✅ Target time reached: {datetime.now().strftime('%H:%M:%S')}[/green]")

    if temp_post_total_processed > 0 or temp_post_total_failed > 0:
        console.print(f"   [cyan]📝 Temp posts during wait: {temp_post_total_processed} processed, {temp_post_total_failed} failed[/cyan]")

    return True


def wait_until_morning_start():
    """Wait until 08:00 AM to start the daily workflow.

    If current time is before 08:00 AM, wait.
    If current time is after 08:00 AM, return immediately.

    Returns:
        True if waited, False if started immediately
    """
    now = datetime.now()
    target = now.replace(hour=settings.daily_start_hour, minute=0, second=0, microsecond=0)

    if now.hour >= settings.daily_start_hour:
        return False  # Already past 08:00, start immediately

    # Calculate wait time
    wait_seconds = (target - now).total_seconds()

    console.print(f"\n[bold yellow]🌅 Waiting until {settings.daily_start_hour:02d}:00 to start daily workflow...[/bold yellow]")
    console.print(f"   Current time: {now.strftime('%H:%M:%S')}")
    console.print(f"   Wait time: {int(wait_seconds // 3600)}h {int((wait_seconds % 3600) // 60)}m")

    while datetime.now() < target:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            break
        sleep_time = min(60, remaining)
        time.sleep(sleep_time)

        # Show status every 30 minutes
        remaining_after = (target - datetime.now()).total_seconds()
        if int(remaining // 1800) != int(remaining_after // 1800):
            console.print(f"   ⏳ {int(remaining_after // 60)} minutes until {settings.daily_start_hour:02d}:00...")

    console.print(f"   [green]✅ {settings.daily_start_hour:02d}:00 reached! Starting daily workflow...[/green]")
    return True


def run_reschedule_procedure():
    """Run the end-of-day reschedule procedure at 23:00.

    Reviews all launch plan files to find undone tasks from the past 3 days.
    Intelligently reschedules them based on:
    - Project guide.md context
    - Cross-project schedule conflicts
    - User's time budget constraints (17h/week for startup projects)

    IMPORTANT RULE: This procedure NEVER removes any tasks from launch plan files.
    - Completed tasks are preserved as project history records
    - Overdue tasks are only marked with "*(moved to Date)*", not deleted
    - All original task content remains intact
    This preserves the complete project timeline and history.

    Returns:
        Tuple of (rescheduled_count, calendar_path)
    """
    console.print("\n[bold magenta]" + "=" * 60 + "[/bold magenta]")
    console.print("[bold magenta]📋 SMART AUTO-RESCHEDULE PROCEDURE (23:00)[/bold magenta]")
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]\n")

    # Load project directories from config
    # Projects are configured in config/projects.yaml or via environment variables
    project_dirs = {}
    for project in settings.projects:
        project_dirs[project["name"]] = project["path"]

    # Weekly time budget for startup projects (in hours)
    # Users should customize this based on their projects
    # Default: equal distribution among configured projects
    num_projects = len(project_dirs)
    default_hours = 17 // max(num_projects, 1)  # 17 hours/week total
    project_weekly_hours = {name: default_hours for name in project_dirs}

    # Daily max hours per project (weekly / 7, rounded up for flexibility)
    project_daily_max = {k: max(1, v / 5) for k, v in project_weekly_hours.items()}  # 5 working days

    today = datetime.now().date()
    three_days_ago = today - timedelta(days=2)

    # Step 1: Read project contexts from guide.md files
    console.print("[bold]📚 Step 1: Reading project contexts...[/bold]\n")
    project_contexts = {}
    for project_name, project_path in project_dirs.items():
        guide_path = Path(project_path) / ".claude" / "guide.md"
        if guide_path.exists():
            try:
                with open(guide_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract first 500 chars as summary
                    project_contexts[project_name] = content[:500]
                console.print(f"  ✅ {project_name}: guide.md loaded")
            except Exception as e:
                console.print(f"  ⚠️  {project_name}: Failed to read guide.md - {e}")
        else:
            console.print(f"  ℹ️  {project_name}: No guide.md found")

    # Step 2: Collect all scheduled tasks across projects for conflict detection
    console.print("\n[bold]📅 Step 2: Collecting existing schedules for conflict detection...[/bold]\n")
    existing_schedules = {}  # date -> list of (project, task, duration)

    for project_name, project_path in project_dirs.items():
        project_dir = Path(project_path)
        if not project_dir.exists():
            continue

        for file_path in project_dir.rglob("*.md"):
            filename_lower = file_path.name.lower()
            if "launch" in filename_lower and "plan" in filename_lower:
                if "_archived_" in str(file_path):
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Parse scheduled tasks
                    current_date = None
                    for line in content.split('\n'):
                        day_match = re.match(r'^\*\*Day\s+\d+\s*\(([^)]+)\)\*\*', line)
                        if day_match:
                            current_date = _parse_reschedule_date(day_match.group(1))
                        elif current_date and re.match(r'^\s*[-*]?\s*\[.\]', line):
                            # Extract duration if present
                            duration_match = re.search(r'(\d+\.?\d*)\s*h', line)
                            duration = float(duration_match.group(1)) if duration_match else 1.0
                            date_key = current_date.date() if hasattr(current_date, 'date') else current_date
                            if date_key not in existing_schedules:
                                existing_schedules[date_key] = []
                            existing_schedules[date_key].append((project_name, line.strip()[:50], duration))
                except:
                    pass

    # Step 3: Find undone tasks from past 3 days
    console.print("[bold]🔍 Step 3: Scanning for undone tasks from past 3 days...[/bold]\n")
    undone_tasks = []

    for project_name, project_path in project_dirs.items():
        project_dir = Path(project_path)
        if not project_dir.exists():
            console.print(f"  ⚠️  {project_name}: Directory not found")
            continue

        launch_files = []
        for file_path in project_dir.rglob("*.md"):
            filename_lower = file_path.name.lower()
            if "launch" in filename_lower and "plan" in filename_lower:
                if "_archived_" not in str(file_path):
                    launch_files.append(file_path)

        if not launch_files:
            console.print(f"  ℹ️  {project_name}: No launch plan files")
            continue

        console.print(f"  📁 {project_name}:")

        for file_path in launch_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                current_day_date = None
                current_day_header_line = None
                file_undone = []

                for i, line in enumerate(lines):
                    day_header_match = re.match(r'^(\*\*Day\s+\d+\s*\([^)]+\)\*\*.*)$', line, re.IGNORECASE)
                    if day_header_match:
                        date_part_match = re.search(r'\(([^)]+)\)', line)
                        if date_part_match:
                            parsed_date = _parse_reschedule_date(date_part_match.group(1))
                            if parsed_date:
                                current_day_date = parsed_date
                                current_day_header_line = i
                        continue

                    completion_markers = ['✅', 'COMPLETED', '[x]', '[X]', 'done]', '[done', 'moved', 'postponed', '❌']
                    if any(marker.lower() in line.lower() for marker in completion_markers):
                        continue

                    incomplete_match = re.match(r'^(\s*[-*]?\s*\[\s*\])\s*(.+)$', line)
                    if incomplete_match and current_day_date:
                        task_date = current_day_date.date() if hasattr(current_day_date, 'date') else current_day_date
                        if isinstance(task_date, datetime):
                            task_date = task_date.date()

                        if three_days_ago <= task_date <= today:
                            task_title = incomplete_match.group(2).strip()
                            duration_match = re.search(r'(\d+\.?\d*)\s*h', task_title)
                            duration = float(duration_match.group(1)) if duration_match else 1.0

                            if len(task_title) >= 10:
                                file_undone.append({
                                    'project': project_name,
                                    'file': file_path,
                                    'line_num': i,
                                    'line': line,
                                    'task': task_title,
                                    'original_date': current_day_date,
                                    'duration': duration,
                                    'day_header_line': current_day_header_line,
                                })

                if file_undone:
                    console.print(f"      📄 {file_path.name}: {len(file_undone)} undone task(s)")
                    undone_tasks.extend(file_undone)

            except Exception as e:
                console.print(f"      ⚠️  Error reading {file_path.name}: {e}")

    if not undone_tasks:
        console.print("\n[green]✅ No undone tasks found from the past 3 days![/green]")
        console.print("\n[bold]📅 Regenerating calendar...[/bold]")
        cal_generator = CalendarGenerator()
        output_file = cal_generator.generate_calendar()
        # Upload to configured destinations
        upload_calendar(output_file)
        return 0, output_file

    console.print(f"\n[yellow]📋 Found {len(undone_tasks)} undone task(s) from past 3 days[/yellow]")

    # Display undone tasks
    console.print("\n[bold]Undone Tasks:[/bold]")
    for i, task in enumerate(undone_tasks, 1):
        date_str = task['original_date'].strftime('%m/%d') if hasattr(task['original_date'], 'strftime') else str(task['original_date'])
        console.print(f"  {i}. [{task['project']}] {date_str} ({task['duration']}h): {task['task'][:45]}...")

    # Step 4: Smart rescheduling with conflict detection
    console.print("\n[bold]🧠 Step 4: Smart rescheduling with conflict detection...[/bold]\n")

    console.print("[dim]Time Budget Constraints:[/dim]")
    console.print("[dim]  - 4To1 Planner: ~2h/day (10h/week)[/dim]")
    console.print("[dim]  - FIRE API: ~1.4h/day (7h/week)[/dim]")
    console.print("[dim]  - Total startup: 17h/week[/dim]\n")

    # Group undone tasks by project
    tasks_by_project = {}
    for task in undone_tasks:
        if task['project'] not in tasks_by_project:
            tasks_by_project[task['project']] = []
        tasks_by_project[task['project']].append(task)

    # Calculate rescheduled dates
    rescheduled_tasks = []
    tomorrow = today + timedelta(days=1)

    for project_name, tasks in tasks_by_project.items():
        daily_max = project_daily_max.get(project_name, 2)  # Default 2h/day
        current_date = tomorrow
        daily_hours_used = 0

        for task in tasks:
            # Check if adding this task exceeds daily limit
            if daily_hours_used + task['duration'] > daily_max:
                # Move to next day
                current_date += timedelta(days=1)
                daily_hours_used = 0

            # Check for conflicts with existing schedule
            while True:
                date_schedule = existing_schedules.get(current_date, [])
                project_hours = sum(d for p, t, d in date_schedule if p == project_name)

                if project_hours + task['duration'] <= daily_max:
                    break
                current_date += timedelta(days=1)
                daily_hours_used = 0

            task['new_date'] = current_date
            daily_hours_used += task['duration']
            rescheduled_tasks.append(task)

            console.print(f"  📅 [{task['project']}] {task['original_date'].strftime('%m/%d')} → {current_date.strftime('%m/%d')}: {task['task'][:40]}...")

    # Step 5: Actually update the launch plan files
    # IMPORTANT: This step ONLY adds markers - it NEVER removes any tasks!
    # All completed and overdue tasks are preserved as project history.
    console.print("\n[bold]✏️  Step 5: Updating launch plan files...[/bold]")
    console.print("[dim]   (Note: Tasks are only marked, never removed - preserving project history)[/dim]\n")

    files_modified = set()
    tasks_marked = 0
    for task in rescheduled_tasks:
        file_path = task['file']
        new_date = task['new_date']

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            original_line_count = len(lines)

            # Find or create the target day section
            new_date_str = new_date.strftime('%b %d').replace(' 0', ' ')  # "Dec 18" format

            # Find the line with this task and add a "moved" marker inside the [ ] checkbox
            # IMPORTANT: We only ADD markers to existing lines, never remove any content
            task_line = task['line_num']
            if task_line < len(lines):
                original_line = lines[task_line]
                # Add moved marker inside the checkbox (only if not already marked)
                if '[ ]' in original_line and '[moved to' not in original_line:
                    # Mark as moved with new date inside the checkbox - preserving original task text
                    moved_line = original_line.replace('[ ]', f'[moved to {new_date_str}]')
                    lines[task_line] = moved_line
                    tasks_marked += 1

            # Safety check: ensure we're not removing any lines
            if len(lines) < original_line_count:
                console.print(f"  [red]❌ SAFETY CHECK FAILED: Would remove lines from {file_path.name} - ABORTING[/red]")
                continue

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            files_modified.add(file_path)

        except Exception as e:
            console.print(f"  ⚠️  Failed to update {file_path.name}: {e}")

    for file_path in files_modified:
        console.print(f"  ✅ Updated: {file_path.name}")

    # Step 6: Regenerate calendar and upload
    console.print("\n[bold]📅 Step 6: Regenerating calendar with updated schedule...[/bold]")
    cal_generator = CalendarGenerator()
    output_file = cal_generator.generate_calendar()

    # Upload to configured destinations
    upload_calendar(output_file)

    console.print(f"\n[green]{'=' * 60}[/green]")
    console.print(f"[bold green]✅ SMART RESCHEDULE COMPLETE![/bold green]")
    console.print(f"[green]{'=' * 60}[/green]")
    console.print(f"   Tasks rescheduled: {len(rescheduled_tasks)}")
    console.print(f"   Tasks marked: {tasks_marked}")
    console.print(f"   Files modified: {len(files_modified)}")
    console.print(f"   Calendar updated: {output_file}")
    console.print(f"\n[cyan]📜 History preserved: All past tasks remain in files (completed & overdue)[/cyan]")
    console.print(f"[cyan]💡 Tip: Review the launch plan files to verify the rescheduled tasks.[/cyan]")

    return len(rescheduled_tasks), output_file


def _parse_reschedule_date(date_str: str):
    """Parse date from day header for reschedule."""
    # Remove day of week suffix
    date_str = re.sub(r'\s*-\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*$', '', date_str, flags=re.IGNORECASE)
    date_str = date_str.strip()

    # Parse "Dec 1" or "December 1"
    month_day_match = re.match(
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
        date_str, re.IGNORECASE
    )

    if month_day_match:
        month_str = month_day_match.group(1)
        day = int(month_day_match.group(2))

        month_map = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4, 'may': 5,
            'june': 6, 'jun': 6, 'july': 7, 'jul': 7, 'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
            'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
        }

        month = month_map.get(month_str.lower())
        if month:
            year = datetime.now().year
            current_month = datetime.now().month
            if month < current_month:
                year += 1
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

    return None


@cli.command('mcp-publish')
@click.option('--platforms', '-p', default='twitter,linkedin', help='Comma-separated list of platforms (twitter,linkedin,mastodon)')
@click.option('--file', '-f', type=click.Path(exists=True), help='Markdown file to publish')
@click.option('--content', '-c', help='Content to publish directly')
@click.option('--check', is_flag=True, help='Check MCP server status only')
def mcp_publish(platforms: str, file: str, content: str, check: bool):
    """Publish to multiple platforms via MCP server.

    Supports: Twitter/X, LinkedIn, Mastodon

    Examples:
        ./bip mcp-publish --check
        ./bip mcp-publish -f data/temp_posts/my_post/post.md -p twitter,linkedin
        ./bip mcp-publish -c "Hello world!" -p twitter
    """
    try:
        from src.publishers.mcp_publisher import MCPPublisher, check_mcp_status
    except ImportError as e:
        console.print(f"[red]❌ MCP publisher not available: {e}[/red]")
        console.print("[yellow]Install: cd mcp-servers/social-media-mcp && npm install && npm run build[/yellow]")
        return

    if check:
        check_mcp_status()
        return

    if not file and not content:
        console.print("[red]❌ Please provide --file or --content[/red]")
        return

    # Read content from file if provided
    if file:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        console.print(f"[dim]📄 Read content from: {file}[/dim]")

    # Parse platforms
    platform_list = [p.strip().lower() for p in platforms.split(',')]
    console.print(f"[dim]📤 Publishing to: {', '.join(platform_list)}[/dim]")

    try:
        publisher = MCPPublisher()

        # Check configuration
        config = publisher.check_configuration()
        unconfigured = [p for p in platform_list if not config.get(p, False)]
        if unconfigured:
            console.print(f"[yellow]⚠️  These platforms are not configured: {', '.join(unconfigured)}[/yellow]")
            console.print("[dim]Edit: mcp-servers/social-media-mcp/.env[/dim]")

        # Publish
        result = publisher.publish(content, platforms=platform_list)

        if result.get('success'):
            console.print("[green]✅ Published successfully![/green]")
            if result.get('urls'):
                for platform, url in result['urls'].items():
                    console.print(f"   {platform}: {url}")
        else:
            console.print(f"[red]❌ Publish failed: {result.get('error', 'Unknown error')}[/red]")

    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


@cli.command('schedule')
@click.option('--status', is_flag=True, help='Show schedule summary')
@click.option('--publish-due', is_flag=True, help='Publish all due posts now')
@click.option('--upcoming', default=24, help='Show posts scheduled in next N hours')
@click.option('--list', 'list_posts', is_flag=True, help='List temp posts available for scheduling')
@click.option('--add', 'add_folder', help='Add a temp post folder to schedule')
@click.option('--platforms', default='twitter', help='Platforms to publish to (comma-separated)')
def schedule(status: bool, publish_due: bool, upcoming: int, list_posts: bool, add_folder: str, platforms: str):
    """Manage post scheduling.

    Examples:
        ./bip schedule --status                      # Show schedule summary
        ./bip schedule --publish-due                 # Publish all due posts
        ./bip schedule --upcoming 48                 # Show posts in next 48 hours
        ./bip schedule --list                        # List temp posts ready for scheduling
        ./bip schedule --add "folder_name"           # Schedule a temp post
        ./bip schedule --add "folder" --platforms twitter  # Schedule for Twitter only
    """
    from src.schedulers.post_scheduler import PostScheduler, print_schedule_summary

    scheduler = PostScheduler()

    if status:
        print_schedule_summary()
        return

    if publish_due:
        console.print("\n[bold]📤 Publishing due posts...[/bold]")
        published, failed = scheduler.process_due_posts()
        console.print(f"\n[green]✅ Published: {published}[/green]")
        if failed > 0:
            console.print(f"[red]❌ Failed: {failed}[/red]")
        return

    if list_posts:
        console.print("\n[bold]📁 Temp posts available for scheduling:[/bold]\n")
        posts = list_temp_posts_for_scheduling()

        if not posts:
            console.print("[dim]No temp posts found (run ./bip temp-post first)[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Folder Name")
        table.add_column("Has Images")
        table.add_column("Scheduled")
        table.add_column("Post ID")

        for p in posts:
            table.add_row(
                p["folder_name"],
                "✅" if p["has_images"] else "❌",
                "✅" if p["already_scheduled"] else "❌",
                str(p["post_id"]) if p["post_id"] else "-"
            )

        console.print(table)
        console.print(f"\n[dim]To schedule: ./bip schedule --add \"folder_name\"[/dim]")
        return

    if add_folder:
        console.print(f"\n[bold]📅 Scheduling temp post: {add_folder}[/bold]\n")
        platform_list = [p.strip() for p in platforms.split(',')]
        success = schedule_temp_post(add_folder, platform_list)
        if success:
            console.print(f"\n[green]✅ Post scheduled successfully![/green]")
        return

    # Default: show upcoming posts
    console.print(f"\n[bold]📅 Posts scheduled in next {upcoming} hours:[/bold]")
    posts = scheduler.get_upcoming_posts(hours=upcoming)

    if not posts:
        console.print("[dim]No upcoming scheduled posts[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Scheduled At")
    table.add_column("Platforms")
    table.add_column("Source")
    table.add_column("Content Preview")

    for post in posts:
        platforms = ", ".join(post.scheduled_platforms) if post.scheduled_platforms else "N/A"
        preview = post.content[:50] + "..." if len(post.content) > 50 else post.content
        preview = preview.replace("\n", " ")

        table.add_row(
            str(post.id),
            post.scheduled_publish_at.strftime("%Y-%m-%d %H:%M") if post.scheduled_publish_at else "N/A",
            platforms,
            post.schedule_source or "N/A",
            preview
        )

    console.print(table)

    # Also show due posts
    due_posts = scheduler.get_due_posts()
    if due_posts:
        console.print(f"\n[yellow]⚠️  {len(due_posts)} post(s) are due for publishing now![/yellow]")
        console.print("[dim]Run: ./bip schedule --publish-due[/dim]")


@cli.command('schedule-all')
def schedule_all():
    """Display ALL scheduled posts (not just next 24 hours).

    Shows every post with status=scheduled, ordered by scheduled time.

    Example: ./bip schedule-all
    """
    from src.schedulers.post_scheduler import PostScheduler

    scheduler = PostScheduler()
    posts = scheduler.get_all_scheduled_posts()

    console.print("\n[bold]📅 All Scheduled Posts:[/bold]\n")

    if not posts:
        console.print("[dim]No scheduled posts found[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Scheduled At")
    table.add_column("Platforms")
    table.add_column("Source")
    table.add_column("Content Preview")

    now = datetime.now()
    for post in posts:
        platforms = ", ".join(post.scheduled_platforms) if post.scheduled_platforms else "N/A"
        preview = post.content[:50] + "..." if len(post.content) > 50 else post.content
        preview = preview.replace("\n", " ")

        # Determine if due or upcoming
        if post.scheduled_publish_at and post.scheduled_publish_at <= now:
            status = "[yellow]⏰ DUE[/yellow]"
        else:
            status = "[green]📅 Scheduled[/green]"

        table.add_row(
            str(post.id),
            status,
            post.scheduled_publish_at.strftime("%Y-%m-%d %H:%M") if post.scheduled_publish_at else "N/A",
            platforms,
            post.schedule_source or "N/A",
            preview
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(posts)} scheduled post(s)[/dim]")


@cli.command('schedule-unpublished')
def schedule_unpublished():
    """Display all unpublished posts (both due and future scheduled).

    Shows posts that are scheduled but haven't been published yet.
    Useful for seeing your complete publishing queue.

    Example: ./bip schedule-unpublished
    """
    from src.schedulers.post_scheduler import PostScheduler

    scheduler = PostScheduler()
    posts = scheduler.get_all_unpublished_posts()

    console.print("\n[bold]📋 Unpublished Posts (Due + Future):[/bold]\n")

    if not posts:
        console.print("[dim]No unpublished scheduled posts found[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Scheduled At")
    table.add_column("Time Until")
    table.add_column("Platforms")
    table.add_column("Content Preview")

    now = datetime.now()
    due_count = 0
    future_count = 0

    for post in posts:
        platforms = ", ".join(post.scheduled_platforms) if post.scheduled_platforms else "N/A"
        preview = post.content[:40] + "..." if len(post.content) > 40 else post.content
        preview = preview.replace("\n", " ")

        # Calculate time until publishing
        if post.scheduled_publish_at:
            if post.scheduled_publish_at <= now:
                time_until = "[yellow]OVERDUE[/yellow]"
                status = "[yellow]⏰ DUE NOW[/yellow]"
                due_count += 1
            else:
                delta = post.scheduled_publish_at - now
                hours = delta.total_seconds() / 3600
                if hours < 24:
                    time_until = f"{hours:.1f}h"
                else:
                    days = hours / 24
                    time_until = f"{days:.1f}d"
                status = "[green]📅 Pending[/green]"
                future_count += 1
        else:
            time_until = "N/A"
            status = "[dim]Unknown[/dim]"

        table.add_row(
            str(post.id),
            status,
            post.scheduled_publish_at.strftime("%Y-%m-%d %H:%M") if post.scheduled_publish_at else "N/A",
            time_until,
            platforms,
            preview
        )

    console.print(table)
    console.print(f"\n[dim]Summary: {due_count} due now, {future_count} future scheduled[/dim]")

    if due_count > 0:
        console.print(f"\n[yellow]⚠️  {due_count} post(s) are due for publishing![/yellow]")
        console.print("[dim]Run: ./bip schedule --publish-due[/dim]")


@cli.command('daily-auto')
@click.option('--collect-time', default="20:00", help='Time for collect (HH:MM format)')
@click.option('--select-time', default="20:30", help='Time for select (HH:MM format)')
@click.option('--skip-publish', is_flag=True, help='Skip auto-publish step')
def daily_auto(collect_time: str, select_time: str, skip_publish: bool):
    """Run fully automated 24/7 daily workflow with scheduled times.

    This command runs the complete daily workflow automatically:
    - 08:00 AM: Start daily workflow (waits if before 08:00)
    - meeting: immediately after 08:00
    - calendar: immediately after meeting
    - temp-post: immediately after calendar + hourly during wait
    - collect: at specified time (default 20:00)
    - generate: immediately after collect
    - select: at specified time (default 20:30)
    - publish: immediately after select
    - 23:00 PM: Reschedule undone tasks + regenerate calendar
    - Next day 08:00 AM: Restart entire workflow (24/7 loop)

    Example: ./bip daily-auto --collect-time 20:00 --select-time 20:30
    """
    console.print(Panel(
        "[bold]🤖 DAILY-AUTO: Fully Automated 24/7 Build-in-Public Workflow[/bold]\n\n"
        "This will run the complete workflow automatically in a 24/7 loop:\n"
        "• 08:00 AM: Start (waits if before 08:00)\n"
        "• meeting → calendar → temp-post → 🎨images → 📅auto-schedule → (hourly check) → collect → generate → select → 🎨image → publish\n"
        "• 23:00 PM: Reschedule undone tasks\n"
        "• Next 08:00 AM: Restart entire workflow\n\n"
        f"[cyan]Daily start: {settings.daily_start_hour:02d}:00[/cyan]\n"
        f"[cyan]Collect time: {collect_time}[/cyan]\n"
        f"[cyan]Select time: {select_time}[/cyan]\n"
        f"[cyan]Reschedule: {settings.reschedule_hour:02d}:00[/cyan]\n"
        f"[cyan]Auto-publish: {'No (skipped)' if skip_publish else 'Yes'}[/cyan]\n"
        f"[cyan]Image generation: Automatic (Gemini Imagen 3)[/cyan]",
        title="🌅 Daily Auto (24/7)",
        border_style="green"
    ))

    # Parse times
    try:
        collect_hour, collect_min = map(int, collect_time.split(':'))
        select_hour, select_min = map(int, select_time.split(':'))
    except ValueError:
        console.print("[red]❌ Invalid time format. Use HH:MM (e.g., 20:00)[/red]")
        return

    # Step 0: Wait until 08:00 AM if before
    if wait_until_morning_start():
        console.print("[green]✅ Morning start time reached[/green]")
    else:
        console.print(f"[yellow]⚠️  Already past {settings.daily_start_hour:02d}:00, starting immediately[/yellow]")

    start_time = datetime.now()
    console.print(f"\n[bold]🚀 Daily workflow started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}[/bold]\n")

    # ========================================
    # Step 1: Meeting (immediately) - Skip if already generated today
    # ========================================
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]📋 STEP 1: Morning Meeting (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    existing_meeting = check_today_meeting_exists()
    if existing_meeting:
        console.print(f"[yellow]⏭️  Today's meeting already exists: {existing_meeting.name}[/yellow]")
        console.print("[cyan]ℹ️  Skipping meeting generation, moving to next step...[/cyan]")
    else:
        try:
            manager = MeetingManager()
            report, text, filepath = manager.run_meeting()
            console.print(Markdown(text))
            console.print(f"\n[green]✅ Meeting complete. Report: {filepath}[/green]")
        except Exception as e:
            console.print(f"[red]❌ Meeting failed: {e}[/red]")

    # ========================================
    # Step 2: Calendar (immediately after meeting)
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]📅 STEP 2: Generate Calendar (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    try:
        cal_generator = CalendarGenerator()
        output_file = cal_generator.generate_calendar()
        if output_file:
            console.print(f"[green]✅ Calendar generated: {output_file}[/green]")
            # Upload to configured destinations
            upload_calendar(output_file)
        else:
            console.print("[yellow]⚠️  No tasks with dates found[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Calendar generation failed: {e}[/red]")

    # ========================================
    # Step 2.5: Initial Temp-Post Check (immediately after calendar)
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]📝 STEP 2.5: Initial Temp-Post Check (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    try:
        processed, failed = run_temp_post_check()
        if processed > 0:
            console.print(f"[green]✅ Processed {processed} temp post(s)[/green]")
        else:
            console.print(f"[cyan]ℹ️  No new temp posts to process[/cyan]")
        if failed > 0:
            console.print(f"[yellow]⚠️  {failed} temp post(s) failed[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Temp-post check failed: {e}[/red]")

    # ========================================
    # Step 2.6: Generate Images for Temp Posts (immediately after temp-post)
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]🎨 STEP 2.6: Generate Images for Posts (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    try:
        img_processed, img_failed, img_skipped = run_image_generation()
        if img_processed > 0:
            console.print(f"[green]✅ Generated images for {img_processed} post(s)[/green]")
        else:
            console.print(f"[cyan]ℹ️  No new images to generate[/cyan]")
        if img_failed > 0:
            console.print(f"[yellow]⚠️  {img_failed} image generation(s) failed[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Image generation failed: {e}[/red]")

    # ========================================
    # Step 2.7: Auto-schedule temp posts (immediate after images)
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]📅 STEP 2.7: Auto-Schedule Temp Posts (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    try:
        sched_success, sched_failed = auto_schedule_temp_posts()
        if sched_success > 0:
            console.print(f"[green]✅ Scheduled {sched_success} temp post(s) for publishing[/green]")
        else:
            console.print(f"[cyan]ℹ️  No temp posts to schedule[/cyan]")
        if sched_failed > 0:
            console.print(f"[yellow]⚠️  {sched_failed} scheduling(s) failed[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Auto-scheduling failed: {e}[/red]")

    # ========================================
    # Step 2.8: Publish Due Posts (immediate check before wait)
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]📤 STEP 2.8: Publish Due Posts (immediate)[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    # Check if publishing is disabled (via flag or config)
    if skip_publish or not settings.auto_post_enabled:
        console.print(f"[yellow]⏭️  Auto-publish disabled (skip_publish={skip_publish}, auto_post_enabled={settings.auto_post_enabled})[/yellow]")
        console.print("[cyan]ℹ️  Posts are saved and scheduled, but not published automatically[/cyan]")
        console.print("[dim]   To publish manually: ./bip schedule --publish-due[/dim]")
    else:
        try:
            from src.schedulers.post_scheduler import PostScheduler
            scheduler = PostScheduler()
            due_posts = scheduler.get_due_posts()

            if due_posts:
                console.print(f"[bold yellow]📤 {len(due_posts)} scheduled post(s) due for publishing...[/bold yellow]")
                published, failed = scheduler.process_due_posts()
                if published > 0:
                    console.print(f"[green]✅ Published {published} scheduled post(s)[/green]")
                if failed > 0:
                    console.print(f"[red]❌ Failed to publish {failed} post(s)[/red]")
            else:
                console.print(f"[cyan]ℹ️  No scheduled posts due for publishing[/cyan]")
        except Exception as e:
            console.print(f"[red]❌ Due post check failed: {e}[/red]")

    # ========================================
    # Step 3: Wait until collect time (with hourly temp-post checks), then collect + generate
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print(f"[bold cyan]📦 STEP 3: Collect Data (at {collect_time})[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")

    # Check if collect time has passed
    now = datetime.now()
    target_collect = now.replace(hour=collect_hour, minute=collect_min, second=0, microsecond=0)

    if now < target_collect:
        wait_until_time_with_hourly_check(collect_hour, collect_min)
    else:
        console.print(f"\n[yellow]⚠️  Collect time {collect_time} has passed. Running now.[/yellow]")

    # Collect data
    console.print("\n[bold]📦 Collecting data...[/bold]")
    aggregator = DataAggregator()
    data = aggregator.collect_all_data()
    highlights = aggregator.get_highlights(data)

    if highlights['total_commits'] == 0:
        console.print("[yellow]⚠️  No activity found. Generating posts anyway...[/yellow]")

    # Generate posts immediately after collect
    console.print(f"\n[bold]✨ Generating {settings.posts_per_day} posts...[/bold]")
    generator = PostGenerator()
    posts = generator.generate_multiple_posts(data, count=settings.posts_per_day)

    # Save posts to database
    session = get_session()
    saved_records = []
    for post in posts:
        record = PostRecord(
            generation_date=datetime.now(),
            content=post.content,
            style=post.style.value,
            language=post.language.value,
            hashtags=post.hashtags,
            word_count=post.word_count,
            projects_mentioned=post.projects_mentioned,
            technical_keywords=post.technical_keywords,
            source_data=data.model_dump(mode='json'),
            generation_metadata=post.metadata,
            status=PostStatus.DRAFT.value,
        )
        session.add(record)
        saved_records.append(record)
    session.commit()
    console.print(f"[green]✅ Generated and saved {len(posts)} posts to database[/green]")

    # Auto-save ALL posts to selected_posts directory
    console.print(f"\n[bold]📁 Auto-saving all {len(saved_records)} posts to selected_posts/...[/bold]")
    for record in saved_records:
        try:
            filepath = save_post_to_markdown(record)
            console.print(f"   ✅ Saved: {filepath.name}")
        except Exception as e:
            console.print(f"   [yellow]⚠️  Failed to save post #{record.id}: {e}[/yellow]")

    # ========================================
    # Step 4: Wait until select time, then select + publish
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print(f"[bold cyan]👆 STEP 4: Auto-Select Post (at {select_time})[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")

    # Check if select time has passed
    now = datetime.now()
    target_select = now.replace(hour=select_hour, minute=select_min, second=0, microsecond=0)

    if now < target_select:
        wait_until_time(select_hour, select_min)
    else:
        console.print(f"\n[yellow]⚠️  Select time {select_time} has passed. Running now.[/yellow]")

    # Auto-select post
    selected_post = auto_select_post()

    # ========================================
    # Step 4.5: Generate Image for Selected Post (immediate)
    # ========================================
    if selected_post:
        console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
        console.print("[bold cyan]🎨 STEP 4.5: Generate Image for Selected Post[/bold cyan]")
        console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

        try:
            # Get the post filename from the most recently saved selected post
            selected_posts_dir = Path("data/selected_posts")
            # Find the image-prompt file for this post
            image_prompt_pattern = f"image-prompt_*_id{selected_post.id}.md"
            image_prompt_files = list(selected_posts_dir.glob(image_prompt_pattern))

            if image_prompt_files:
                image_prompt_file = image_prompt_files[0]
                post_name = image_prompt_file.stem.replace("image-prompt_", "")

                # Generate image for this specific post
                generator = ImageGenerator()
                images_folder = Path("data/post-images") / post_name
                images_marker = images_folder / "images.ready"

                if not images_marker.exists():
                    console.print(f"  🎨 Generating image for: {post_name}")

                    # Read prompts from image-prompt file
                    with open(image_prompt_file, 'r', encoding='utf-8') as f:
                        prompt_content = f.read()

                    prompts = generator.extract_image_prompts_from_post(prompt_content, post_name)

                    if prompts:
                        width, height = 1080, 1440  # Xiaohongshu dimensions
                        for prompt_info in prompts:
                            image_name = prompt_info["name"].lower().replace(" ", "_")
                            import re
                            image_name = re.sub(r'[^a-z0-9_]', '', image_name)

                            result = generator.generate_image(
                                prompt=prompt_info["prompt"],
                                output_path=images_folder,
                                image_name=image_name,
                                width=width,
                                height=height,
                                platform="xiaohongshu"
                            )

                            if result.get("success"):
                                console.print(f"  ✅ Image saved: {result['file_path']}")
                                images_marker.parent.mkdir(parents=True, exist_ok=True)
                                images_marker.touch()
                            else:
                                console.print(f"  ❌ Image generation failed: {result.get('error')}")
                    else:
                        console.print(f"  ⚠️  No image prompts found")
                else:
                    console.print(f"  ⏭️  Image already exists for this post")
            else:
                console.print(f"  ⚠️  No image-prompt file found for post #{selected_post.id}")
        except Exception as e:
            console.print(f"  [red]❌ Image generation failed: {e}[/red]")

    # ========================================
    # Step 5: Selected Post Ready for Manual Review
    # ========================================
    # NOTE: Auto-publish for selected posts has been removed (Task 62).
    # Selected posts stay as SELECTED status for manual review and posting.
    # Use ./bip schedule --add to schedule temp posts for auto-publishing.
    if selected_post:
        console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
        console.print("[bold cyan]📋 STEP 5: Selected Post Ready for Review[/bold cyan]")
        console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
        console.print(f"\n[green]✅ Post #{selected_post.id} is ready for manual review[/green]")
        console.print("[dim]   Selected posts are NOT auto-published.[/dim]")
        console.print("[dim]   Review in data/selected_posts/ and post manually.[/dim]")

    # ========================================
    # Step 6: Continuous Temp-Post Monitoring
    # ========================================
    console.print("\n[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]🔄 STEP 6: Continuous Temp-Post Monitoring[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")

    console.print("\n[bold yellow]📝 Now monitoring for new temp posts...[/bold yellow]")
    console.print("   Checking every hour for new folders in data/temp_posts/")
    console.print("   [cyan]Press Ctrl+C to stop monitoring and exit[/cyan]\n")

    # Summary of completed workflow
    workflow_end_time = datetime.now()
    workflow_duration = workflow_end_time - start_time

    console.print("=" * 60)
    console.print("[bold green]✨ DAILY WORKFLOW STAGES COMPLETE![/bold green]")
    console.print("=" * 60)
    console.print(f"   Started: {start_time.strftime('%H:%M:%S')}")
    console.print(f"   Workflow completed: {workflow_end_time.strftime('%H:%M:%S')}")
    console.print(f"   Duration: {workflow_duration}")
    console.print(f"   Posts generated: {len(posts)}")
    if selected_post:
        console.print(f"   Selected post: #{selected_post.id}")
        if selected_post.xhs_url:
            console.print(f"   Published URL: {selected_post.xhs_url}")
    console.print("=" * 60)

    # Continuous monitoring loop with 23:00 reschedule and 08:00 next day restart
    total_temp_processed = 0
    total_temp_failed = 0
    total_img_processed = 0
    total_img_failed = 0
    total_sched_success = 0
    total_sched_failed = 0
    check_count = 0
    reschedule_done_today = False
    day_count = 1

    try:
        while True:
            check_count += 1
            current_time = datetime.now()

            console.print(f"\n[dim]─── Hourly Check #{check_count} ({current_time.strftime('%H:%M:%S')}) ───[/dim]")

            # Check for new temp posts
            processed, failed = run_temp_post_check()
            total_temp_processed += processed
            total_temp_failed += failed

            if processed > 0:
                console.print(f"[green]   ✅ Processed {processed} new temp post(s)[/green]")

                # Generate images for newly processed posts
                console.print(f"[cyan]   🎨 Generating images for new posts...[/cyan]")
                img_proc, img_fail, _ = run_image_generation()
                total_img_processed += img_proc
                total_img_failed += img_fail
                if img_proc > 0:
                    console.print(f"[green]   ✅ Generated images for {img_proc} post(s)[/green]")

                # Auto-schedule posts that now have images
                console.print(f"[cyan]   📅 Auto-scheduling posts...[/cyan]")
                sched_ok, sched_fail = auto_schedule_temp_posts()
                total_sched_success += sched_ok
                total_sched_failed += sched_fail
                if sched_ok > 0:
                    console.print(f"[green]   ✅ Scheduled {sched_ok} post(s) for publishing[/green]")
            else:
                console.print(f"[dim]   No new temp posts[/dim]")

            console.print(f"[dim]   Posts: {total_temp_processed} | Images: {total_img_processed} | Scheduled: {total_sched_success} | Failed: {total_temp_failed + total_img_failed + total_sched_failed}[/dim]")

            # Check for scheduled posts that are due for publishing (if auto-publish enabled)
            if not skip_publish and settings.auto_post_enabled:
                try:
                    from src.schedulers.post_scheduler import PostScheduler
                    scheduler = PostScheduler()
                    due_posts = scheduler.get_due_posts()

                    if due_posts:
                        console.print(f"\n[bold yellow]📤 {len(due_posts)} scheduled post(s) due for publishing...[/bold yellow]")
                        published, failed = scheduler.process_due_posts()
                        if published > 0:
                            console.print(f"[green]   ✅ Published {published} scheduled post(s)[/green]")
                        if failed > 0:
                            console.print(f"[red]   ❌ Failed to publish {failed} post(s)[/red]")
                except Exception as e:
                    console.print(f"[red]   ❌ Scheduler error: {e}[/red]")

            # Check if it's 23:00 or later - time for reschedule procedure
            # We check >= settings.reschedule_hour to catch cases where hourly check happens after 23:00
            if current_time.hour >= settings.reschedule_hour and not reschedule_done_today:
                console.print(f"\n[bold magenta]⏰ {current_time.strftime('%H:%M')} - Running end-of-day reschedule...[/bold magenta]")
                undone_count, cal_path = run_reschedule_procedure()
                reschedule_done_today = True
                console.print(f"[green]✅ Reschedule complete. Undone tasks: {undone_count}[/green]")

            # Check if it's past midnight and before 08:00 - wait for next day start
            if current_time.hour < settings.daily_start_hour:
                console.print(f"\n[bold cyan]🌙 Past midnight. Waiting for {settings.daily_start_hour:02d}:00 to start new daily cycle...[/bold cyan]")

                # Wait until 08:00
                target_morning = current_time.replace(hour=settings.daily_start_hour, minute=0, second=0, microsecond=0)
                while datetime.now() < target_morning:
                    time.sleep(60)

                # New day - restart the workflow
                day_count += 1
                reschedule_done_today = False
                console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
                console.print(f"[bold cyan]🌅 NEW DAILY CYCLE #{day_count} - {datetime.now().strftime('%Y-%m-%d')}[/bold cyan]")
                console.print(f"[bold cyan]{'=' * 60}[/bold cyan]")

                # Run the full daily workflow again
                start_time = datetime.now()
                console.print(f"\n[bold]🚀 Daily workflow restarted at {start_time.strftime('%H:%M:%S')}[/bold]\n")

                # Step 1: Meeting
                console.print("[bold cyan]📋 STEP 1: Morning Meeting[/bold cyan]")
                try:
                    manager = MeetingManager()
                    report, text, filepath = manager.run_meeting()
                    console.print(f"[green]✅ Meeting complete. Report: {filepath}[/green]")
                except Exception as e:
                    console.print(f"[red]❌ Meeting failed: {e}[/red]")

                # Step 2: Calendar
                console.print("\n[bold cyan]📅 STEP 2: Generate Calendar[/bold cyan]")
                try:
                    cal_generator = CalendarGenerator()
                    output_file = cal_generator.generate_calendar()
                    if output_file:
                        console.print(f"[green]✅ Calendar generated: {output_file}[/green]")
                        # Upload to configured destinations
                        upload_calendar(output_file, show_header=False)
                except Exception as e:
                    console.print(f"[red]❌ Calendar failed: {e}[/red]")

                # Step 2.5: Temp-Post Check
                console.print("\n[bold cyan]📝 STEP 2.5: Temp-Post Check[/bold cyan]")
                try:
                    p, f = run_temp_post_check()
                    total_temp_processed += p
                    total_temp_failed += f
                    console.print(f"[green]✅ Processed {p} temp post(s)[/green]")
                except Exception as e:
                    console.print(f"[red]❌ Temp-post check failed: {e}[/red]")

                # Step 2.6: Image Generation
                console.print("\n[bold cyan]🎨 STEP 2.6: Generate Images[/bold cyan]")
                try:
                    ip, if_, _ = run_image_generation()
                    total_img_processed += ip
                    total_img_failed += if_
                    console.print(f"[green]✅ Generated images for {ip} post(s)[/green]")
                except Exception as e:
                    console.print(f"[red]❌ Image generation failed: {e}[/red]")

                # Step 3: Wait for collect time
                console.print(f"\n[bold cyan]📦 STEP 3: Waiting for collect time ({collect_time})[/bold cyan]")
                now = datetime.now()
                target_collect = now.replace(hour=collect_hour, minute=collect_min, second=0, microsecond=0)
                if now < target_collect:
                    wait_until_time_with_hourly_check(collect_hour, collect_min)

                # Collect and generate
                console.print("\n[bold]📦 Collecting data...[/bold]")
                aggregator = DataAggregator()
                data = aggregator.collect_all_data()

                console.print(f"\n[bold]✨ Generating {settings.posts_per_day} posts...[/bold]")
                generator = PostGenerator()
                posts = generator.generate_multiple_posts(data, count=settings.posts_per_day)

                session = get_session()
                saved_records = []
                for post in posts:
                    record = PostRecord(
                        generation_date=datetime.now(),
                        content=post.content,
                        style=post.style.value,
                        language=post.language.value,
                        hashtags=post.hashtags,
                        word_count=post.word_count,
                        projects_mentioned=post.projects_mentioned,
                        technical_keywords=post.technical_keywords,
                        source_data=data.model_dump(mode='json'),
                        generation_metadata=post.metadata,
                        status=PostStatus.DRAFT.value,
                    )
                    session.add(record)
                    saved_records.append(record)
                session.commit()
                console.print(f"[green]✅ Generated and saved {len(posts)} posts to database[/green]")

                # Auto-save ALL posts to selected_posts directory
                console.print(f"\n[bold]📁 Auto-saving all {len(saved_records)} posts to selected_posts/...[/bold]")
                for record in saved_records:
                    try:
                        filepath = save_post_to_markdown(record)
                        console.print(f"   ✅ Saved: {filepath.name}")
                    except Exception as e:
                        console.print(f"   [yellow]⚠️  Failed to save post #{record.id}: {e}[/yellow]")

                # Step 4: Wait for select time
                console.print(f"\n[bold cyan]👆 STEP 4: Waiting for select time ({select_time})[/bold cyan]")
                now = datetime.now()
                target_select = now.replace(hour=select_hour, minute=select_min, second=0, microsecond=0)
                if now < target_select:
                    wait_until_time(select_hour, select_min)

                selected_post = auto_select_post()

                # Step 4.5: Generate Image for Selected Post
                if selected_post:
                    console.print("\n[bold cyan]🎨 STEP 4.5: Generate Image for Selected Post[/bold cyan]")
                    try:
                        selected_posts_dir = Path("data/selected_posts")
                        image_prompt_pattern = f"image-prompt_*_id{selected_post.id}.md"
                        image_prompt_files = list(selected_posts_dir.glob(image_prompt_pattern))

                        if image_prompt_files:
                            image_prompt_file = image_prompt_files[0]
                            post_name = image_prompt_file.stem.replace("image-prompt_", "")
                            generator = ImageGenerator()
                            images_folder = Path("data/post-images") / post_name
                            images_marker = images_folder / "images.ready"

                            if not images_marker.exists():
                                with open(image_prompt_file, 'r', encoding='utf-8') as f:
                                    prompt_content = f.read()
                                prompts = generator.extract_image_prompts_from_post(prompt_content, post_name)
                                if prompts:
                                    for prompt_info in prompts:
                                        image_name = prompt_info["name"].lower().replace(" ", "_")
                                        import re
                                        image_name = re.sub(r'[^a-z0-9_]', '', image_name)
                                        result = generator.generate_image(
                                            prompt=prompt_info["prompt"],
                                            output_path=images_folder,
                                            image_name=image_name,
                                            width=1080, height=1440,
                                            platform="xiaohongshu"
                                        )
                                        if result.get("success"):
                                            console.print(f"  ✅ Image saved: {result['file_path']}")
                                            images_marker.parent.mkdir(parents=True, exist_ok=True)
                                            images_marker.touch()
                    except Exception as e:
                        console.print(f"  [red]❌ Image generation failed: {e}[/red]")

                # Step 5: Selected Post Ready for Manual Review
                # NOTE: Auto-publish for selected posts removed (Task 62)
                if selected_post:
                    console.print("\n[bold cyan]📋 STEP 5: Selected Post Ready for Review[/bold cyan]")
                    console.print(f"[green]✅ Post #{selected_post.id} ready for manual review[/green]")

                console.print("\n[bold green]✨ Daily workflow complete! Continuing monitoring...[/bold green]")
                continue

            console.print(f"[dim]   Next check in 1 hour... (Ctrl+C to exit)[/dim]")

            # Wait for 1 hour
            time.sleep(3600)

    except KeyboardInterrupt:
        # User pressed Ctrl+C
        console.print("\n\n" + "=" * 60)
        console.print("[bold yellow]🛑 MONITORING STOPPED BY USER[/bold yellow]")
        console.print("=" * 60)

        end_time = datetime.now()
        total_duration = end_time - start_time

        console.print(f"\n[bold]📊 Final Summary:[/bold]")
        console.print(f"   Total runtime: {total_duration}")
        console.print(f"   Daily cycles completed: {day_count}")
        console.print(f"   Hourly checks performed: {check_count}")
        console.print(f"   Temp posts processed: {total_temp_processed}")
        console.print(f"   Temp posts failed: {total_temp_failed}")
        console.print(f"\n[bold green]✨ DAILY-AUTO SESSION ENDED[/bold green]")


if __name__ == "__main__":
    cli()
