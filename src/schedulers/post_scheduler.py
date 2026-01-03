"""Post scheduling system for the BIP daily-auto workflow.

This module handles:
- Finding optimal time slots for posting
- Scheduling posts for future publishing
- Checking and publishing due posts
- Managing daily quota per platform
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Tuple
from pathlib import Path

from src.models import PostRecord, PostStatus, get_session
from src.config import settings, bip_settings


class PostScheduler:
    """Scheduler for managing post publishing times."""

    # Default platforms if none specified (Twitter only for temp posts)
    DEFAULT_PLATFORMS = ["twitter"]

    def __init__(self):
        """Initialize the scheduler."""
        self.session = get_session()

        # Load scheduling settings from bip_settings (Tier 3)
        self._scheduling = bip_settings.scheduling

    @property
    def OPTIMAL_SLOTS(self) -> dict:
        """Get optimal posting times from config."""
        return bip_settings.posting_schedules

    @property
    def DAILY_QUOTA(self) -> int:
        """Get daily quota from config."""
        return self._scheduling.get("daily_quota", 2)

    @property
    def MAX_DAYS_AHEAD(self) -> int:
        """Get max days ahead from config."""
        return self._scheduling.get("max_days_ahead", 30)

    def _parse_time_slot(self, slot: str) -> time:
        """Parse a time slot string to a time object.

        Args:
            slot: Time string in HH:MM format

        Returns:
            time object
        """
        return datetime.strptime(slot, "%H:%M").time()

    def _get_scheduled_posts_for_date(
        self,
        date: datetime,
        platform: str = None
    ) -> List[PostRecord]:
        """Get all scheduled posts for a specific date.

        Args:
            date: The date to check
            platform: Optional platform filter

        Returns:
            List of scheduled posts
        """
        start_of_day = datetime.combine(date.date(), time.min)
        end_of_day = datetime.combine(date.date() + timedelta(days=1), time.min)

        query = self.session.query(PostRecord).filter(
            PostRecord.scheduled_publish_at >= start_of_day,
            PostRecord.scheduled_publish_at < end_of_day,
            PostRecord.status == PostStatus.SCHEDULED.value
        )

        posts = query.all()

        # Filter by platform if specified
        if platform:
            posts = [
                p for p in posts
                if p.scheduled_platforms and platform in p.scheduled_platforms
            ]

        return posts

    def _get_used_slots_for_date(
        self,
        date: datetime,
        platform: str
    ) -> List[datetime]:
        """Get already used time slots for a date and platform.

        Args:
            date: The date to check
            platform: The platform to check

        Returns:
            List of used datetime slots
        """
        posts = self._get_scheduled_posts_for_date(date, platform)
        return [p.scheduled_publish_at for p in posts if p.scheduled_publish_at]

    def get_scheduled_count_for_date(
        self,
        date: datetime,
        platform: str
    ) -> int:
        """Get count of scheduled posts for a date and platform.

        Args:
            date: The date to check
            platform: The platform to check

        Returns:
            Number of scheduled posts
        """
        return len(self._get_scheduled_posts_for_date(date, platform))

    def find_next_available_slot(
        self,
        platform: str,
        start_from: datetime = None
    ) -> Optional[datetime]:
        """Find the next available time slot for a platform.

        Args:
            platform: Platform to schedule for
            start_from: Start searching from this datetime (default: now)

        Returns:
            Next available datetime slot, or None if no slots available
        """
        if platform not in self.OPTIMAL_SLOTS:
            print(f"  ⚠️  Unknown platform: {platform}, using default slots")
            slots = bip_settings.get_platform_schedule("default")
        else:
            slots = self.OPTIMAL_SLOTS[platform]

        if start_from is None:
            start_from = datetime.now()

        for day_offset in range(self.MAX_DAYS_AHEAD):
            check_date = start_from + timedelta(days=day_offset)

            # Get count for this date
            scheduled_count = self.get_scheduled_count_for_date(check_date, platform)

            if scheduled_count >= self.DAILY_QUOTA:
                # Daily quota filled, try next day
                continue

            # Get used slots for this date
            used_slots = self._get_used_slots_for_date(check_date, platform)
            used_times = [s.time() for s in used_slots]

            # Find an unused slot
            for slot_str in slots:
                slot_time = self._parse_time_slot(slot_str)
                slot_datetime = datetime.combine(check_date.date(), slot_time)

                # Skip if slot is in the past
                if slot_datetime <= datetime.now():
                    continue

                # Skip if slot is already used
                if slot_time in used_times:
                    continue

                return slot_datetime

        return None  # No available slots in the next MAX_DAYS_AHEAD days

    def schedule_post(
        self,
        post: PostRecord,
        platforms: List[str] = None,
        source: str = "manual"
    ) -> Optional[datetime]:
        """Schedule a post for the next available slot.

        Args:
            post: PostRecord to schedule
            platforms: List of platforms to publish to
            source: Source of the post ("temp_post", "daily_selected", "manual")

        Returns:
            Scheduled datetime, or None if scheduling failed
        """
        if platforms is None:
            platforms = self.DEFAULT_PLATFORMS

        # Find the earliest available slot across all platforms
        earliest_slot = None
        for platform in platforms:
            slot = self.find_next_available_slot(platform)
            if slot:
                if earliest_slot is None or slot < earliest_slot:
                    earliest_slot = slot

        if earliest_slot is None:
            print(f"  ❌ No available slots found for platforms: {platforms}")
            return None

        # Update the post record
        post.scheduled_publish_at = earliest_slot
        post.scheduled_platforms = platforms
        post.schedule_source = source
        post.status = PostStatus.SCHEDULED.value

        self.session.commit()

        print(f"  📅 Scheduled for {earliest_slot.strftime('%Y-%m-%d %H:%M')}")
        print(f"     Platforms: {', '.join(platforms)}")

        # Create schedule.ready marker for temp posts
        if source == "temp_post":
            self._create_schedule_marker(post)

        return earliest_slot

    def get_due_posts(self) -> List[PostRecord]:
        """Get all posts that are due for publishing.

        Returns:
            List of posts that should be published now
        """
        now = datetime.now()

        posts = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value,
            PostRecord.scheduled_publish_at <= now,
            PostRecord.scheduled_publish_at.isnot(None)
        ).order_by(PostRecord.scheduled_publish_at).all()

        return posts

    def get_upcoming_posts(self, hours: int = 24) -> List[PostRecord]:
        """Get posts scheduled for the next N hours.

        Args:
            hours: Number of hours to look ahead

        Returns:
            List of upcoming scheduled posts
        """
        now = datetime.now()
        future = now + timedelta(hours=hours)

        posts = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value,
            PostRecord.scheduled_publish_at > now,
            PostRecord.scheduled_publish_at <= future,
            PostRecord.scheduled_publish_at.isnot(None)
        ).order_by(PostRecord.scheduled_publish_at).all()

        return posts

    def publish_post(
        self,
        post: PostRecord,
        create_marker: bool = True
    ) -> Dict[str, any]:
        """Publish a scheduled post to its platforms.

        Args:
            post: PostRecord to publish
            create_marker: Whether to create publish.ready marker file

        Returns:
            Dictionary with publish results per platform
        """
        results = {}
        platforms = post.scheduled_platforms or self.DEFAULT_PLATFORMS

        for platform in platforms:
            try:
                if platform == "twitter":
                    result = self._publish_to_twitter(post)
                elif platform == "xiaohongshu":
                    result = self._publish_to_xiaohongshu(post)
                else:
                    result = {"success": False, "error": f"Unknown platform: {platform}"}

                results[platform] = result

            except Exception as e:
                results[platform] = {"success": False, "error": str(e)}

        # Update post status if any platform succeeded
        any_success = any(r.get("success", False) for r in results.values())
        if any_success:
            post.status = PostStatus.PUBLISHED.value
            post.published_at = datetime.now()
            self.session.commit()

            # Create marker file if requested
            if create_marker and post.schedule_source == "temp_post":
                self._create_publish_marker(post)

        return results

    def _find_post_images(self, post: PostRecord) -> List[str]:
        """Find images associated with a post.

        Args:
            post: PostRecord to find images for

        Returns:
            List of image file paths
        """
        image_paths = []

        # Check if post has folder_path in metadata (temp_post)
        if post.generation_metadata and "folder_path" in post.generation_metadata:
            folder_path = Path(post.generation_metadata["folder_path"])
            images_folder = folder_path / "images"

            if images_folder.exists():
                # Look for common image files
                for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif"]:
                    image_paths.extend([str(p) for p in images_folder.glob(ext)])

                # Prioritize cover image
                cover_candidates = ["cover.png", "cover.jpg", "cover_image.png"]
                for cover in cover_candidates:
                    cover_path = images_folder / cover
                    if cover_path.exists():
                        # Move cover to front of list
                        str_cover = str(cover_path)
                        if str_cover in image_paths:
                            image_paths.remove(str_cover)
                        image_paths.insert(0, str_cover)
                        break

        # Limit to 4 images (Twitter max)
        return image_paths[:4]

    def _publish_to_twitter(self, post: PostRecord) -> Dict[str, any]:
        """Publish post to Twitter via MCP.

        Args:
            post: PostRecord to publish

        Returns:
            Publish result
        """
        try:
            from src.publishers.mcp_publisher import MCPPublisher
            publisher = MCPPublisher()

            # Find images for this post
            image_paths = self._find_post_images(post)
            if image_paths:
                print(f"  📷 Found {len(image_paths)} image(s) to attach")

            result = publisher.publish_to_twitter(post.content, media_paths=image_paths)

            if result.get("success"):
                post.twitter_post_id = result.get("postId")
                post.twitter_url = result.get("url")
                post.twitter_published_at = datetime.now()
                self.session.commit()

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _publish_to_xiaohongshu(self, post: PostRecord) -> Dict[str, any]:
        """Publish post to Xiaohongshu via Playwright.

        Args:
            post: PostRecord to publish

        Returns:
            Publish result
        """
        try:
            from src.publishers.xiaohongshu import XiaohongshuPublisher
            publisher = XiaohongshuPublisher()

            # Extract title from first line
            title = post.content.split('\n')[0][:50] if post.content else "Post"

            result = publisher.publish(
                content=post.content,
                title=title
            )

            if result.get("success"):
                post.xhs_post_id = result.get("post_id")
                post.xhs_url = result.get("url")
                self.session.commit()

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_schedule_marker(self, post: PostRecord) -> bool:
        """Create schedule.ready marker file for a temp post.

        Args:
            post: PostRecord that was scheduled

        Returns:
            True if marker created successfully
        """
        try:
            # Find the temp post folder based on generation metadata
            if post.generation_metadata and "folder_path" in post.generation_metadata:
                folder_path = Path(post.generation_metadata["folder_path"])
                if folder_path.exists():
                    marker_path = folder_path / "schedule.ready"
                    marker_path.touch()
                    print(f"  📋 Created schedule.ready marker")
                    return True

            return False

        except Exception as e:
            print(f"  ⚠️  Failed to create schedule marker: {e}")
            return False

    def _create_publish_marker(self, post: PostRecord) -> bool:
        """Create publish.ready marker file for a temp post.

        Args:
            post: PostRecord that was published

        Returns:
            True if marker created successfully
        """
        try:
            # Find the temp post folder based on generation metadata
            if post.generation_metadata and "folder_path" in post.generation_metadata:
                folder_path = Path(post.generation_metadata["folder_path"])
                if folder_path.exists():
                    marker_path = folder_path / "publish.ready"
                    marker_path.touch()
                    return True

            return False

        except Exception as e:
            print(f"  ⚠️  Failed to create publish marker: {e}")
            return False

    def process_due_posts(self) -> Tuple[int, int]:
        """Process all posts that are due for publishing.

        Returns:
            Tuple of (published_count, failed_count)
        """
        due_posts = self.get_due_posts()

        if not due_posts:
            return 0, 0

        published = 0
        failed = 0

        for post in due_posts:
            print(f"\n📤 Publishing scheduled post #{post.id}...")
            print(f"   Scheduled for: {post.scheduled_publish_at}")
            print(f"   Platforms: {post.scheduled_platforms}")

            results = self.publish_post(post)

            # Check results
            for platform, result in results.items():
                if result.get("success"):
                    print(f"   ✅ {platform}: Published successfully")
                    if result.get("url"):
                        print(f"      URL: {result['url']}")
                    published += 1
                else:
                    print(f"   ❌ {platform}: {result.get('error', 'Unknown error')}")
                    failed += 1

        return published, failed

    def get_all_scheduled_posts(self) -> List[PostRecord]:
        """Get ALL scheduled posts (regardless of time).

        Returns:
            List of all scheduled posts ordered by scheduled time
        """
        posts = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value,
            PostRecord.scheduled_publish_at.isnot(None)
        ).order_by(PostRecord.scheduled_publish_at).all()

        return posts

    def get_all_unpublished_posts(self) -> List[PostRecord]:
        """Get all unpublished posts (both due and future scheduled).

        Returns:
            List of posts that are scheduled but not yet published
        """
        # Get scheduled posts (not yet published)
        scheduled = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value,
            PostRecord.scheduled_publish_at.isnot(None)
        ).order_by(PostRecord.scheduled_publish_at).all()

        return scheduled

    def get_schedule_summary(self) -> Dict[str, any]:
        """Get a summary of the current schedule.

        Returns:
            Dictionary with schedule statistics
        """
        now = datetime.now()
        today = now.date()

        # Count by status
        scheduled_count = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value
        ).count()

        # Count due posts
        due_count = len(self.get_due_posts())

        # Count today's posts per platform
        today_by_platform = {}
        for platform in self.OPTIMAL_SLOTS.keys():
            count = self.get_scheduled_count_for_date(now, platform)
            today_by_platform[platform] = count

        # Get next scheduled post
        next_post = self.session.query(PostRecord).filter(
            PostRecord.status == PostStatus.SCHEDULED.value,
            PostRecord.scheduled_publish_at > now
        ).order_by(PostRecord.scheduled_publish_at).first()

        return {
            "total_scheduled": scheduled_count,
            "due_now": due_count,
            "today_by_platform": today_by_platform,
            "next_post": {
                "id": next_post.id if next_post else None,
                "scheduled_at": next_post.scheduled_publish_at if next_post else None,
                "platforms": next_post.scheduled_platforms if next_post else None
            } if next_post else None
        }


def print_schedule_summary():
    """Print a summary of the current schedule."""
    scheduler = PostScheduler()
    summary = scheduler.get_schedule_summary()

    print("\n📅 Schedule Summary")
    print("=" * 40)
    print(f"Total scheduled: {summary['total_scheduled']}")
    print(f"Due for publishing: {summary['due_now']}")
    print("\nToday's quota:")
    for platform, count in summary['today_by_platform'].items():
        quota = PostScheduler.DAILY_QUOTA
        remaining = max(0, quota - count)
        print(f"  {platform}: {count}/{quota} ({remaining} slots available)")

    if summary['next_post']:
        next_post = summary['next_post']
        print(f"\nNext scheduled post: #{next_post['id']}")
        print(f"  Time: {next_post['scheduled_at']}")
        print(f"  Platforms: {next_post['platforms']}")
    else:
        print("\nNo upcoming scheduled posts")


if __name__ == "__main__":
    print_schedule_summary()
