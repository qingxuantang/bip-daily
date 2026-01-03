"""X.com (Twitter) publisher using Playwright automation."""

import time
import json
from pathlib import Path
from typing import Optional, Dict
from playwright.sync_api import sync_playwright, Page, Browser

from src.config import settings


class TwitterPublisher:
    """Publish posts to X.com (Twitter) using browser automation."""

    def __init__(self):
        """Initialize publisher."""
        self.username = settings.twitter_username
        self.password = settings.twitter_password
        self.cookie_file = Path(settings.base_dir) / settings.twitter_cookie_file
        self.headless = settings.environment == "production"
        # Premium accounts can post up to 25,000 characters
        self.max_chars = 25000

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
        """Login to X.com (Twitter).

        Args:
            page: Playwright page object

        Returns:
            True if login successful
        """
        print("   🔐 Logging in to X.com...")

        # Try loading existing cookies first
        if self._load_cookies(page):
            page.goto("https://x.com/home")
            time.sleep(3)

            # Check if already logged in
            if self._is_logged_in(page):
                print("   ✅ Already logged in (using cookies)")
                return True

        # Manual login required
        page.goto("https://x.com/i/flow/login")
        time.sleep(2)

        print("\n" + "=" * 60)
        print("⚠️  MANUAL LOGIN REQUIRED")
        print("=" * 60)
        print("Please complete the following steps:")
        print("1. Enter your username/email/phone in the browser window")
        print("2. Enter your password")
        print("3. Complete any 2FA or verification if required")
        print("4. Wait until you see your home timeline")
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
            # Look for compose tweet button or timeline
            selectors = [
                'a[data-testid="SideNav_NewTweet_Button"]',
                'div[data-testid="primaryColumn"]',
                'a[aria-label="Profile"]',
                'div[aria-label="Timeline: Your Home Timeline"]',
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
        images: Optional[list] = None,
    ) -> Dict[str, str]:
        """Publish a post to X.com (Twitter).

        Args:
            content: Post content (up to 25,000 chars for Premium)
            images: Optional list of image paths (up to 4 images)

        Returns:
            Dictionary with post_id and url
        """
        print("\n📤 Publishing to X.com (Twitter)...\n")

        # Truncate content if needed
        if len(content) > self.max_chars:
            print(f"   ⚠️  Content truncated from {len(content)} to {self.max_chars} characters")
            content = content[:self.max_chars-3] + "..."

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                locale='en-US',
            )
            page = context.new_page()

            try:
                # Login
                if not self._login(page):
                    raise Exception("Login failed")

                # Navigate to home page
                print("   📝 Opening compose dialog...")
                page.goto("https://x.com/home")
                time.sleep(2)

                # Click the compose button or use compose URL
                try:
                    # Try clicking the "Post" button
                    compose_button = page.locator('a[data-testid="SideNav_NewTweet_Button"]').first
                    if compose_button.count() > 0:
                        compose_button.click()
                        time.sleep(1)
                    else:
                        # Alternative: go to compose URL
                        page.goto("https://x.com/compose/tweet")
                        time.sleep(2)
                except Exception as e:
                    print(f"   ⚠️  Using compose URL fallback: {e}")
                    page.goto("https://x.com/compose/tweet")
                    time.sleep(2)

                # Fill in content
                print("   ✍️  Filling in content...")

                # Find the tweet compose box
                # X.com uses various selectors for the compose box
                compose_selectors = [
                    'div[data-testid="tweetTextarea_0"]',
                    'div[role="textbox"][contenteditable="true"]',
                    'div.public-DraftEditor-content',
                ]

                compose_box = None
                for selector in compose_selectors:
                    if page.locator(selector).count() > 0:
                        compose_box = page.locator(selector).first
                        break

                if compose_box:
                    compose_box.click()
                    time.sleep(0.5)
                    compose_box.fill(content)
                    time.sleep(1)
                else:
                    print("   ⚠️  Could not find compose box, will require manual input")

                # Upload images if provided
                if images:
                    print(f"   📸 Uploading {len(images)} images...")
                    try:
                        # Find the file input for images (usually hidden)
                        upload_input = page.locator('input[data-testid="fileInput"]').first

                        if upload_input.count() == 0:
                            # Alternative selector
                            upload_input = page.locator('input[type="file"][accept*="image"]').first

                        if upload_input.count() > 0:
                            # X.com allows up to 4 images
                            upload_images = images[:4]
                            upload_input.set_input_files(upload_images)
                            time.sleep(2)
                        else:
                            print("   ⚠️  Could not find image upload input")
                    except Exception as e:
                        print(f"   ⚠️  Image upload failed: {e}")

                # Pause for manual review
                print("\n" + "=" * 60)
                print("⚠️  MANUAL REVIEW")
                print("=" * 60)
                print("Please review the post in the browser:")
                print("1. Check the content")
                print("2. Add any additional media or polls if needed")
                print("3. Click the 'Post' button when ready")
                print("4. Return here and press ENTER after posting")
                print("=" * 60)

                input("\nPress ENTER after you've clicked 'Post'...")

                # Wait for post to complete and get URL
                time.sleep(3)

                # Try to find the post URL
                # After posting, Twitter usually redirects to the tweet page
                # or we can find it in the timeline
                post_url = None
                post_id = None

                try:
                    # Wait for navigation or URL change
                    time.sleep(2)
                    current_url = page.url

                    # Check if URL contains status (tweet ID)
                    if "/status/" in current_url:
                        post_url = current_url
                        post_id = current_url.split("/status/")[1].split("?")[0]
                    else:
                        # Try to find the tweet in the timeline
                        # Look for the most recent tweet link
                        tweet_links = page.locator('a[href*="/status/"]').all()
                        if tweet_links:
                            first_link = tweet_links[0]
                            href = first_link.get_attribute('href')
                            if href:
                                post_url = f"https://x.com{href}" if href.startswith('/') else href
                                if "/status/" in post_url:
                                    post_id = post_url.split("/status/")[1].split("?")[0]
                except Exception as e:
                    print(f"   ⚠️  Could not extract post URL automatically: {e}")

                # If we couldn't get the URL automatically, ask the user
                if not post_url:
                    print("\n" + "=" * 60)
                    print("Please copy the tweet URL from your browser")
                    print("=" * 60)
                    post_url = input("Paste the tweet URL here (or press ENTER to skip): ").strip()

                    if post_url and "/status/" in post_url:
                        try:
                            post_id = post_url.split("/status/")[1].split("?")[0]
                        except:
                            pass

                print(f"\n   ✅ Post published!")
                if post_url:
                    print(f"   URL: {post_url}")

                return {
                    "post_id": post_id,
                    "url": post_url or page.url,
                }

            except Exception as e:
                print(f"\n   ❌ Publishing failed: {e}")
                raise

            finally:
                # Keep browser open for a moment
                time.sleep(2)
                browser.close()


class MockTwitterPublisher:
    """Mock publisher for testing without real Twitter account."""

    def publish(self, content: str, images: Optional[list] = None) -> Dict[str, str]:
        """Mock publish.

        Args:
            content: Post content
            images: Optional list of image paths

        Returns:
            Mock response
        """
        print("🧪 [MOCK MODE] Simulating X.com (Twitter) publish...")
        print(f"   Content: {len(content)} chars")
        if images:
            print(f"   Images: {len(images)} files")

        # Generate mock post ID
        import hashlib
        post_id = hashlib.md5(content.encode()).hexdigest()[:16]

        return {
            "post_id": post_id,
            "url": f"https://x.com/user/status/{post_id}",
        }


if __name__ == "__main__":
    # Test publisher
    print("🧪 Testing X.com (Twitter) Publisher\n")

    # Use mock publisher for testing
    publisher = MockTwitterPublisher()

    result = publisher.publish(
        content="This is a test post for Build-in-Public!\n\n#BuildInPublic #IndieHacker"
    )

    print(f"\n✅ Published:")
    print(f"   Post ID: {result['post_id']}")
    print(f"   URL: {result['url']}")
