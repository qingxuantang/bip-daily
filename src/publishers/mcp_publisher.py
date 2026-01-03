"""MCP-based multi-platform social media publisher.

This module provides integration with the social-media-mcp server for publishing
to Twitter, LinkedIn, and Mastodon through the Model Context Protocol.
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.config import settings


class MCPPublisher:
    """Publish posts to multiple social media platforms via MCP server."""

    # Supported platforms by the MCP server
    SUPPORTED_PLATFORMS = ["twitter", "linkedin", "mastodon"]

    def _get_node_path(self) -> str:
        """Get the path to a Node.js version that supports ES modules (v12+).

        The system /usr/bin/node may be an old version (e.g., v10) that doesn't
        support ES modules. This method tries to find a newer Node.js version.

        Returns:
            Path to a suitable Node.js binary
        """
        import shutil

        # Priority 1: Check nvm-managed node in home directory
        home = Path.home()
        nvm_node_dir = home / ".nvm" / "versions" / "node"
        if nvm_node_dir.exists():
            # Find the highest version available
            versions = sorted(nvm_node_dir.iterdir(), reverse=True)
            for version_dir in versions:
                node_bin = version_dir / "bin" / "node"
                if node_bin.exists():
                    # Check if version is 12+ (supports ES modules)
                    version_str = version_dir.name.lstrip('v').split('.')[0]
                    try:
                        if int(version_str) >= 12:
                            return str(node_bin)
                    except ValueError:
                        continue

        # Priority 2: Check if 'node' in PATH is v12+
        node_in_path = shutil.which("node")
        if node_in_path:
            try:
                result = subprocess.run(
                    [node_in_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version_str = result.stdout.strip().lstrip('v').split('.')[0]
                if int(version_str) >= 12:
                    return node_in_path
            except (subprocess.TimeoutExpired, ValueError):
                pass

        # Fallback: just use 'node' and hope for the best
        return "node"

    def __init__(self):
        """Initialize the MCP publisher."""
        self.mcp_server_path = Path(settings.base_dir) / "mcp-servers" / "social-media-mcp"
        self.mcp_index_path = self.mcp_server_path / "build" / "index.js"
        self.env_file = self.mcp_server_path / ".env"

        # Check if MCP server is installed
        if not self.mcp_index_path.exists():
            raise FileNotFoundError(
                f"MCP server not found at {self.mcp_index_path}. "
                "Run: cd mcp-servers/social-media-mcp && npm install && npm run build"
            )

    def _load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from MCP server .env file.

        Returns:
            Dictionary of environment variables
        """
        env_vars = os.environ.copy()

        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Handle ${VAR} references to BIP .env
                        if value.startswith('${') and value.endswith('}'):
                            ref_var = value[2:-1]
                            value = getattr(settings, ref_var.lower(), '') or os.environ.get(ref_var, '')
                        env_vars[key] = value

        return env_vars

    def _call_mcp_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via the server.

        Args:
            tool_name: Name of the MCP tool to call
            args: Arguments for the tool

        Returns:
            Tool response as dictionary
        """
        # Prepare the MCP request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            }
        }

        env_vars = self._load_env_vars()

        # Get Node.js path that supports ES modules (v12+)
        node_path = self._get_node_path()

        try:
            # Call the MCP server
            result = subprocess.run(
                [node_path, str(self.mcp_index_path)],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                env=env_vars,
                timeout=60
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or "MCP server error"
                }

            # Parse response - filter out log lines, find JSON response
            # MCP server outputs logs to stdout before the JSON response
            stdout = result.stdout
            json_response = None

            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('{"result":') or line.startswith('{"jsonrpc":'):
                    json_response = line
                    break

            if not json_response:
                # Try parsing the whole output as JSON (fallback)
                try:
                    response = json.loads(stdout)
                    return response.get("result", response)
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": f"No JSON response found in output. First 500 chars: {stdout[:500]}"
                    }

            response = json.loads(json_response)
            return response.get("result", response)

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "MCP server timeout"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON response: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish(
        self,
        content: str,
        platforms: List[str] = None,
        post_immediately: bool = True,
        media_paths: List[str] = None
    ) -> Dict[str, Any]:
        """Publish content to social media platforms.

        Args:
            content: The post content to publish
            platforms: List of platforms to publish to (default: all supported)
            post_immediately: Whether to post immediately or return preview
            media_paths: Optional list of image paths to attach (for Twitter)

        Returns:
            Dictionary with publish results for each platform
        """
        if platforms is None:
            platforms = self.SUPPORTED_PLATFORMS

        # Validate platforms
        invalid = [p for p in platforms if p not in self.SUPPORTED_PLATFORMS]
        if invalid:
            return {
                "success": False,
                "error": f"Unsupported platforms: {invalid}. Supported: {self.SUPPORTED_PLATFORMS}"
            }

        results = {}

        # Use direct posting for Twitter (bypasses MCP conversation flow)
        if "twitter" in platforms:
            print(f"📤 Publishing to Twitter via direct API...")
            if media_paths:
                print(f"   📷 {len(media_paths)} image(s) to attach")
            twitter_result = self._post_to_twitter_direct(content, media_paths)
            results["twitter"] = twitter_result
            if not twitter_result.get("success"):
                return twitter_result

        # For other platforms, use MCP tool (with conversation flow)
        other_platforms = [p for p in platforms if p != "twitter"]
        if other_platforms:
            print(f"📤 Publishing to {', '.join(other_platforms)} via MCP server...")
            mcp_result = self._call_mcp_tool("create_post", {
                "instruction": content,
                "platforms": other_platforms,
                "postImmediately": post_immediately
            })
            results["mcp"] = mcp_result

        # Return combined results
        if len(results) == 1:
            return list(results.values())[0]

        return {
            "success": all(r.get("success", False) for r in results.values()),
            "results": results
        }

    def _post_to_twitter_direct(
        self,
        content: str,
        media_paths: List[str] = None
    ) -> Dict[str, Any]:
        """Post directly to Twitter using the direct-post.js script.

        Args:
            content: The tweet content
            media_paths: Optional list of image paths to attach

        Returns:
            Post result
        """
        direct_post_script = self.mcp_server_path / "direct-post.js"

        if not direct_post_script.exists():
            return {
                "success": False,
                "error": f"direct-post.js not found at {direct_post_script}"
            }

        env_vars = self._load_env_vars()

        # Get Node.js path that supports ES modules (v12+)
        node_path = self._get_node_path()

        # Build command with content and optional media paths
        cmd = [node_path, str(direct_post_script), content]
        if media_paths:
            # Filter to only existing files
            valid_paths = [p for p in media_paths if Path(p).exists()]
            if valid_paths:
                cmd.extend(valid_paths)
                print(f"   📷 Attaching {len(valid_paths)} image(s)")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env_vars,
                cwd=str(self.mcp_server_path),
                timeout=120  # Increased timeout for media upload
            )

            # Find the JSON output after ---JSON--- marker
            stdout = result.stdout
            if "---JSON---" in stdout:
                json_part = stdout.split("---JSON---")[1].strip()
                return json.loads(json_part)

            # Fallback: check if SUCCESS in output
            if "SUCCESS!" in stdout:
                # Try to extract tweet ID from output
                import re
                tweet_id_match = re.search(r'Tweet ID: (\d+)', stdout)
                url_match = re.search(r'URL: (https://[^\s]+)', stdout)
                return {
                    "success": True,
                    "postId": tweet_id_match.group(1) if tweet_id_match else None,
                    "url": url_match.group(1) if url_match else None
                }

            return {
                "success": False,
                "error": result.stderr or "Unknown error",
                "stdout": stdout[:500]
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Twitter posting timeout"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON response: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def publish_to_twitter(
        self,
        content: str,
        media_paths: List[str] = None
    ) -> Dict[str, Any]:
        """Publish to Twitter/X only, with optional media.

        Args:
            content: The post content
            media_paths: Optional list of image paths to attach (max 4)

        Returns:
            Publish result
        """
        print(f"📤 Publishing to Twitter via direct API...")
        if media_paths:
            # Twitter allows max 4 images per tweet
            media_paths = media_paths[:4]
            print(f"   📷 {len(media_paths)} image(s) to attach")
        return self._post_to_twitter_direct(content, media_paths)

    def publish_to_linkedin(self, content: str) -> Dict[str, Any]:
        """Publish to LinkedIn only.

        Args:
            content: The post content

        Returns:
            Publish result
        """
        return self.publish(content, platforms=["linkedin"])

    def publish_to_mastodon(self, content: str) -> Dict[str, Any]:
        """Publish to Mastodon only.

        Args:
            content: The post content

        Returns:
            Publish result
        """
        return self.publish(content, platforms=["mastodon"])

    def research_topic(
        self,
        topic: str,
        include_hashtags: bool = True,
        include_facts: bool = True,
        include_trends: bool = True,
        include_news: bool = True
    ) -> Dict[str, Any]:
        """Research a topic using the MCP server.

        Args:
            topic: Topic to research
            include_hashtags: Include relevant hashtags
            include_facts: Include facts
            include_trends: Include trends
            include_news: Include news

        Returns:
            Research results
        """
        print(f"🔍 Researching topic: {topic}")

        return self._call_mcp_tool("research_topic", {
            "topic": topic,
            "includeHashtags": include_hashtags,
            "includeFacts": include_facts,
            "includeTrends": include_trends,
            "includeNews": include_news
        })

    def get_trending_topics(
        self,
        platform: str = "twitter",
        category: str = "technology",
        count: int = 5
    ) -> Dict[str, Any]:
        """Get trending topics from a platform.

        Args:
            platform: Platform to get trends from
            category: Topic category
            count: Number of topics to return

        Returns:
            Trending topics
        """
        print(f"📈 Getting trending topics from {platform}...")

        return self._call_mcp_tool("get_trending_topics", {
            "platform": platform,
            "category": category,
            "count": count
        })

    def check_configuration(self) -> Dict[str, bool]:
        """Check which platforms are properly configured.

        Returns:
            Dictionary of platform -> configured status
        """
        env_vars = self._load_env_vars()

        config_status = {
            "twitter": all([
                env_vars.get("TWITTER_API_KEY"),
                env_vars.get("TWITTER_ACCESS_TOKEN")
            ]),
            "linkedin": all([
                env_vars.get("LINKEDIN_CLIENT_ID"),
                env_vars.get("LINKEDIN_ACCESS_TOKEN")
            ]),
            "mastodon": all([
                env_vars.get("MASTODON_ACCESS_TOKEN")
            ]),
            "ai_content": any([
                env_vars.get("ANTHROPIC_API_KEY"),
                env_vars.get("OPENAI_API_KEY")
            ]),
            "research": bool(env_vars.get("BRAVE_API_KEY"))
        }

        return config_status


def check_mcp_status():
    """Check MCP server installation and configuration status."""
    print("\n🔍 MCP Publisher Status Check\n")
    print("=" * 50)

    try:
        publisher = MCPPublisher()
        print("✅ MCP server is installed")

        config = publisher.check_configuration()

        print("\n📋 Platform Configuration:")
        for platform, configured in config.items():
            status = "✅ Configured" if configured else "❌ Not configured"
            print(f"   {platform.title()}: {status}")

        print("\n📝 To configure platforms:")
        print("   1. Edit: mcp-servers/social-media-mcp/.env")
        print("   2. Add your API keys for each platform")
        print("   3. For LinkedIn OAuth, run:")
        print("      cd mcp-servers/social-media-mcp/scripts && npm install && npm run linkedin-oauth")

    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\n📝 To install MCP server:")
        print("   cd mcp-servers/social-media-mcp")
        print("   npm install")
        print("   npm run build")


if __name__ == "__main__":
    check_mcp_status()
