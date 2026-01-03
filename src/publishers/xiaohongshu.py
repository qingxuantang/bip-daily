"""Xiaohongshu publisher using Playwright automation."""

import time
import json
from pathlib import Path
from typing import Optional, Dict
from playwright.sync_api import sync_playwright, Page, Browser

from src.config import settings


class XiaohongshuPublisher:
    """Publish posts to Xiaohongshu using browser automation."""

    def __init__(self):
        """Initialize publisher."""
        self.username = settings.xhs_username
        self.password = settings.xhs_password
        self.cookie_file = Path(settings.base_dir) / settings.xhs_cookie_file
        self.headless = settings.environment == "production"

    def _save_cookies(self, page: Page):
        """Save cookies to file.

        Args:
            page: Playwright page object
        """
        cookies = page.context.cookies()
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.cookie_file, 'w') as f:
            json.dump(cookies, f)

        print(f"   ✅ Cookies saved to {self.cookie_file}")

    def _load_cookies(self, page: Page) -> bool:
        """Load cookies from file.

        Args:
            page: Playwright page object

        Returns:
            True if cookies loaded successfully
        """
        if not self.cookie_file.exists():
            return False

        try:
            with open(self.cookie_file, 'r') as f:
                cookies = json.load(f)

            page.context.add_cookies(cookies)
            print(f"   ✅ Cookies loaded from {self.cookie_file}")
            return True

        except Exception as e:
            print(f"   ⚠️  Failed to load cookies: {e}")
            return False

    def _login(self, page: Page) -> bool:
        """Login to Xiaohongshu.

        Args:
            page: Playwright page object

        Returns:
            True if login successful
        """
        print("   🔐 Logging in to Xiaohongshu...")

        # Try loading existing cookies first
        if self._load_cookies(page):
            page.goto("https://www.xiaohongshu.com/explore")
            time.sleep(3)

            # Check if already logged in
            if self._is_logged_in(page):
                print("   ✅ Already logged in (using cookies)")
                return True

        # Manual login required
        page.goto("https://www.xiaohongshu.com")
        time.sleep(2)

        print("\n" + "=" * 60)
        print("⚠️  MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("Please complete the following steps:")
        print("1. Click the login button in the browser window")
        print("2. Scan QR code or enter username/password")
        print("3. Complete any verification if required")
        print("4. Wait until you see your home feed")
        print("5. Return to this terminal and press ENTER")
        print("=" * 60)

        input("\nPress ENTER after you've logged in...")

        # Verify login
        if self._is_logged_in(page):
            print("   ✅ Login successful!")
            self._save_cookies(page)
            return True
        else:
            print("   ❌ Login verification failed")
            return False

    def _is_logged_in(self, page: Page) -> bool:
        """Check if user is logged in.

        Args:
            page: Playwright page object

        Returns:
            True if logged in
        """
        # Check for common logged-in elements
        try:
            # Look for profile or create button
            selectors = [
                'a[href*="/user/profile"]',
                'button:has-text("发布笔记")',
                'div.avatar',
            ]

            for selector in selectors:
                if page.locator(selector).count() > 0:
                    return True

            return False

        except Exception:
            return False

    def publish(
        self,
        content: str,
        title: str,
        images: Optional[list] = None,
    ) -> Dict[str, str]:
        """Publish a post to Xiaohongshu.

        Args:
            content: Post content
            title: Post title
            images: Optional list of image paths

        Returns:
            Dictionary with post_id and url
        """
        print("\n📤 Publishing to Xiaohongshu...\n")

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                locale='zh-CN',
            )
            page = context.new_page()

            try:
                # Login
                if not self._login(page):
                    raise Exception("Login failed")

                # Navigate to create page
                print("   📝 Opening create page...")
                page.goto("https://creator.xiaohongshu.com/publish/publish")
                time.sleep(3)

                # Check if we need alternative URL
                if "creator.xiaohongshu.com" not in page.url:
                    page.goto("https://www.xiaohongshu.com/user/profile/me")
                    time.sleep(2)

                    # Click create button
                    create_button = page.locator('button:has-text("发布笔记")')
                    if create_button.count() > 0:
                        create_button.click()
                        time.sleep(2)

                # Fill in title and content
                print("   ✍️  Filling in content...")

                # Title
                title_input = page.locator('input[placeholder*="填写标题"]').first
                if title_input.count() > 0:
                    title_input.fill(title[:50])  # Max 50 chars
                    time.sleep(1)

                # Content
                content_area = page.locator('textarea, div[contenteditable="true"]').first
                if content_area.count() > 0:
                    content_area.fill(content)
                    time.sleep(1)

                # Upload images if provided
                if images:
                    print(f"   📸 Uploading {len(images)} images...")
                    upload_input = page.locator('input[type="file"]').first

                    if upload_input.count() > 0:
                        upload_input.set_input_files(images)
                        time.sleep(2)

                # Pause for manual review
                print("\n" + "=" * 60)
                print("⚠️  MANUAL REVIEW")
                print("=" * 60)
                print("Please review the post in the browser:")
                print("1. Check title and content")
                print("2. Add any tags or topics if needed")
                print("3. Click '发布' when ready")
                print("4. Return here and press ENTER after publishing")
                print("=" * 60)

                input("\nPress ENTER after you've clicked '发布'...")

                # Get post URL
                time.sleep(5)
                post_url = page.url

                # Try to extract post ID
                post_id = None
                if "/notes/" in post_url:
                    post_id = post_url.split("/notes/")[1].split("?")[0]

                print(f"\n   ✅ Post published!")

                return {
                    "post_id": post_id,
                    "url": post_url,
                }

            except Exception as e:
                print(f"\n   ❌ Publishing failed: {e}")
                raise

            finally:
                # Keep browser open for a moment
                time.sleep(2)
                browser.close()


class MockXiaohongshuPublisher:
    """Mock publisher for testing without real Xiaohongshu account."""

    def publish(self, content: str, title: str, images: Optional[list] = None) -> Dict[str, str]:
        """Mock publish.

        Args:
            content: Post content
            title: Post title
            images: Optional list of image paths

        Returns:
            Mock response
        """
        print("🧪 [MOCK MODE] Simulating Xiaohongshu publish...")
        print(f"   Title: {title}")
        print(f"   Content: {len(content)} chars")
        if images:
            print(f"   Images: {len(images)} files")

        # Generate mock post ID
        import hashlib
        post_id = hashlib.md5(content.encode()).hexdigest()[:16]

        return {
            "post_id": post_id,
            "url": f"https://www.xiaohongshu.com/explore/{post_id}",
        }


if __name__ == "__main__":
    # Test publisher
    print("🧪 Testing Xiaohongshu Publisher\n")

    # Use mock publisher for testing
    publisher = MockXiaohongshuPublisher()

    result = publisher.publish(
        content="这是一个测试贴文\n\n包含多行内容\n\n#测试 #BuildInPublic",
        title="测试贴文标题"
    )

    print(f"\n✅ Published:")
    print(f"   Post ID: {result['post_id']}")
    print(f"   URL: {result['url']}")
