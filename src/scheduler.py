"""Scheduler for automated daily posting."""

import pytz
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.collectors.aggregator import DataAggregator
from src.generators.post_generator import PostGenerator
from src.publishers.xiaohongshu import XiaohongshuPublisher
from src.models import PostRecord, GenerationLog, get_session, PostStatus
from src.config import settings


class DailyScheduler:
    """Schedule daily post generation and publishing."""

    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = BlockingScheduler()
        self.timezone = pytz.timezone(settings.timezone)

    def daily_generation_job(self):
        """Daily job to generate posts."""
        print(f"\n{'=' * 60}")
        print(f"🌅 Daily Generation Job - {datetime.now()}")
        print('=' * 60)

        session = get_session()
        log = GenerationLog(
            date=datetime.now(),
            posts_generated=0,
            success=False,
        )

        try:
            # Collect data
            print("\n📦 Collecting data...")
            aggregator = DataAggregator(lookback_days=settings.lookback_days)
            data = aggregator.collect_all_data()

            highlights = aggregator.get_highlights(data)

            if highlights['total_commits'] == 0:
                print("⚠️  No activity found. Skipping generation.")
                log.error_message = "No activity"
                log.metadata = highlights
                session.add(log)
                session.commit()
                return

            # Generate posts
            print(f"\n✨ Generating {settings.posts_per_day} posts...")
            generator = PostGenerator()
            posts = generator.generate_multiple_posts(
                data,
                count=settings.posts_per_day
            )

            # Save posts
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

            # Update log
            log.posts_generated = len(posts)
            log.success = True
            log.metadata = {
                "highlights": highlights,
                "posts": [p.style.value for p in posts],
            }

            session.add(log)
            session.commit()

            print(f"\n✅ Generated {len(posts)} posts!")
            print("   Use CLI to select and publish")

        except Exception as e:
            print(f"\n❌ Generation failed: {e}")
            log.error_message = str(e)
            session.add(log)
            session.commit()

    def auto_publish_job(self):
        """Auto-publish selected post (if enabled)."""
        if not settings.auto_post_enabled:
            return

        print(f"\n📤 Auto-publish job - {datetime.now()}")

        session = get_session()

        # Get selected post
        selected_post = session.query(PostRecord).filter_by(
            status=PostStatus.SELECTED.value
        ).order_by(PostRecord.selected_at.desc()).first()

        if not selected_post:
            print("   ⚠️  No selected post found")
            return

        try:
            publisher = XiaohongshuPublisher()
            result = publisher.publish(
                content=selected_post.content,
                title=selected_post.content.split('\n')[0][:50],
            )

            # Update post
            selected_post.status = PostStatus.PUBLISHED.value
            selected_post.published_at = datetime.now()
            selected_post.xhs_post_id = result.get('post_id')
            selected_post.xhs_url = result.get('url')

            session.commit()

            print("   ✅ Published successfully!")

        except Exception as e:
            print(f"   ❌ Publishing failed: {e}")

    def start(self):
        """Start the scheduler."""
        # Parse generation time
        hour, minute = map(int, settings.generation_time.split(':'))

        # Schedule daily generation
        generation_trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=self.timezone
        )

        self.scheduler.add_job(
            self.daily_generation_job,
            trigger=generation_trigger,
            id='daily_generation',
            name='Daily Post Generation',
            replace_existing=True,
        )

        print(f"\n🤖 Scheduler Started")
        print(f"   Timezone: {settings.timezone}")
        print(f"   Generation Time: {settings.generation_time}")
        print(f"   Auto-publish: {settings.auto_post_enabled}")
        print(f"\n⏰ Next run:")

        for job in self.scheduler.get_jobs():
            print(f"   {job.name}: {job.next_run_time}")

        print(f"\n🚀 Running... (Press Ctrl+C to stop)\n")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\n\n👋 Scheduler stopped")


if __name__ == "__main__":
    scheduler = DailyScheduler()
    scheduler.start()
