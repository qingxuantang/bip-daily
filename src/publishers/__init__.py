"""Social media publishers for the BIP system.

Available publishers:
- XiaohongshuPublisher: Publish to Xiaohongshu (小红书) via Playwright
- TwitterPublisher: Publish to X.com/Twitter via Playwright
- MCPPublisher: Publish to Twitter, LinkedIn, Mastodon via MCP server
"""

from src.publishers.xiaohongshu import XiaohongshuPublisher
from src.publishers.twitter import TwitterPublisher

# MCP Publisher (optional - requires MCP server setup)
try:
    from src.publishers.mcp_publisher import MCPPublisher, check_mcp_status
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPPublisher = None
    check_mcp_status = None

__all__ = [
    "XiaohongshuPublisher",
    "TwitterPublisher",
    "MCPPublisher",
    "MCP_AVAILABLE",
    "check_mcp_status",
]
