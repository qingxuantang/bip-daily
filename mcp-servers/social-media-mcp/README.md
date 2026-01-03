# Social Media MCP Server

A Model Context Protocol (MCP) server that connects to multiple social media platforms, allowing users to create and publish content across platforms through natural language instructions.

## Features

- **Natural Language Interface**: Create posts for multiple platforms with simple instructions
- **Research Capabilities**: Automatically research hashtags, trends, facts, and news
- **Multi-platform Support**: Post to Twitter/X, Mastodon, and LinkedIn with platform-specific formatting
- **Content Generation**: Generate engaging content using multiple AI models
- **Rate Limit Management**: Handle API rate limits gracefully with queuing and fallbacks
- **Analytics**: Track post performance and optimize content strategy

## Getting Started

### Prerequisites

- Node.js (v18+)
- npm or yarn
- API keys for:
  - Twitter/X
  - Mastodon
  - LinkedIn
  - OpenAI and/or Anthropic (for content generation)
  - Brave Search (for research)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/social-media-mcp.git
cd social-media-mcp
```

2. Install dependencies:

```bash
npm install
```

3. Create a `.env` file with your API keys:

```
# Twitter API Credentials
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
TWITTER_OAUTH_CLIENT=your_oauth_client
TWITTER_CLIENT_SECRET=your_client_secret

# Mastodon API Credentials
MASTODON_CLIENT_SECRET=your_client_secret
MASTODON_CLIENT_KEY=your_client_key
MASTODON_ACCESS_TOKEN=your_access_token

# LinkedIn API Credentials
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_ACCESS_TOKEN=your_access_token

# AI API Keys
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
BRAVE_API_KEY=your_brave_key

# Application Settings
LOG_LEVEL=info
CACHE_ENABLED=true
RATE_LIMIT_ENABLED=true
```

4. Build the project:

```bash
npm run build
```

5. Start the server:

```bash
npm start
```

### MCP Integration

To use this MCP server with Claude or another MCP-compatible assistant, add it to your MCP settings:

```json
{
  "mcpServers": {
    "social-media-mcp": {
      "command": "node",
      "args": ["path/to/social-media-mcp/build/index.js"],
      "env": {
        "TWITTER_API_KEY": "your_api_key",
        "TWITTER_API_SECRET": "your_api_secret",
        "TWITTER_BEARER_TOKEN": "your_bearer_token",
        "TWITTER_ACCESS_TOKEN": "your_access_token",
        "TWITTER_ACCESS_SECRET": "your_access_secret",
        "TWITTER_OAUTH_CLIENT": "your_oauth_client",
        "TWITTER_CLIENT_SECRET": "your_client_secret",
        "MASTODON_CLIENT_SECRET": "your_client_secret",
        "MASTODON_CLIENT_KEY": "your_client_key",
        "MASTODON_ACCESS_TOKEN": "your_access_token",
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_ACCESS_TOKEN": "your_access_token",
        "ANTHROPIC_API_KEY": "your_anthropic_key",
        "OPENAI_API_KEY": "your_openai_key",
        "BRAVE_API_KEY": "your_brave_key"
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Available Tools

### create_post

Create and post content to social media platforms based on natural language instructions.

```json
{
  "instruction": "Post about the latest AI developments in healthcare",
  "platforms": ["twitter", "mastodon", "linkedin"],
  "postImmediately": false
}
```

### get_trending_topics

Get trending topics from social media platforms.

```json
{
  "platform": "twitter",
  "category": "technology",
  "count": 5
}
```

### research_topic

Research a topic using Brave Search and Perplexity.

```json
{
  "topic": "artificial intelligence ethics",
  "includeHashtags": true,
  "includeFacts": true,
  "includeTrends": true,
  "includeNews": true
}
```

## Development

### Project Structure

```
social-media-mcp/
├── src/
│   ├── index.ts                 # Entry point
│   ├── config/                  # Configuration
│   ├── types/                   # TypeScript type definitions
│   ├── core/                    # Core orchestration logic
│   ├── nlp/                     # Natural language processing
│   ├── research/                # Research engine
│   │   ├── brave/               # Brave Search integration
│   │   ├── perplexity/          # Perplexity integration
│   │   └── aggregator/          # Research result aggregation
│   ├── content/                 # Content generation
│   │   ├── strategies/          # AI model strategies
│   │   ├── formatter/           # Platform-specific formatting
│   │   └── templates/           # Content templates
│   ├── platforms/               # Social media platform integrations
│   │   ├── twitter/             # Twitter API integration
│   │   └── mastodon/            # Mastodon API integration
│   ├── analytics/               # Analytics engine
│   ├── rate-limit/              # Rate limit management
│   └── utils/                   # Utility functions
├── memory-bank/                 # Project documentation
├── build/                       # Compiled JavaScript
├── .env                         # Environment variables
├── package.json                 # Dependencies and scripts
└── tsconfig.json                # TypeScript configuration
```

### Scripts

- `npm run build`: Build the project
- `npm run dev`: Run in development mode with hot reloading
- `npm start`: Start the production server
- `npm test`: Run tests
- `npm run lint`: Run linting
- `npm run format`: Format code

### Utility Scripts

The `scripts` directory contains utility scripts for the Social Media MCP Server:

- `scripts/linkedin-oauth.js`: Handles the OAuth 2.0 flow for LinkedIn to obtain an access token
  - Usage: `cd scripts && npm install && npm run linkedin-oauth`
  - See [scripts/README.md](scripts/README.md) for more details

### Documentation

The `documentation` directory contains detailed documentation for each social media platform integration:

- [Mastodon Integration](documentation/mastodon-integration.md)
- [Twitter Integration](documentation/twitter-integration.md)
- [LinkedIn Integration](documentation/linkedin-integration.md)
- [Integration Summary](documentation/integration-summary.md)

## License

This project is licensed under the ISC License.

## Acknowledgements

- [Model Context Protocol](https://github.com/anthropics/model-context-protocol)
- [Twitter API v2](https://developer.twitter.com/en/docs/twitter-api)
- [Mastodon API](https://docs.joinmastodon.org/api/)
- [LinkedIn API](https://learn.microsoft.com/en-us/linkedin/marketing/getting-started)
