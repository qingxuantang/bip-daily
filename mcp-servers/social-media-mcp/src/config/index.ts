import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { TwitterCredentials, MastodonCredentials, LinkedInCredentials } from '../types/index.js';

// Load environment variables from root .env file
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootEnvPath = path.resolve(__dirname, '../../../../.env');
dotenv.config({ path: rootEnvPath });

// Configuration object
const config = {
  // Server configuration
  server: {
    name: 'social-media-mcp',
    version: '0.1.0',
    logLevel: process.env.LOG_LEVEL || 'info',
  },

  // Twitter API configuration
  twitter: {
    credentials: {
      apiKey: process.env.TWITTER_API_KEY || '',
      apiSecret: process.env.TWITTER_API_SECRET || '',
      bearerToken: process.env.TWITTER_BEARER_TOKEN || '',
      accessToken: process.env.TWITTER_ACCESS_TOKEN || '',
      accessSecret: process.env.TWITTER_ACCESS_SECRET || '',
      oauthClient: process.env.TWITTER_OAUTH_CLIENT || '',
      clientSecret: process.env.TWITTER_CLIENT_SECRET || '',
    } as TwitterCredentials,
    rateLimits: {
      postTweet: 200, // 200 requests per 15-minute window
      timeline: 100,  // 100 requests per 15-minute window
    },
    debug: true, // Enable debug mode for Twitter
  },

  // Mastodon API configuration
  mastodon: {
    credentials: {
      clientSecret: process.env.MASTODON_CLIENT_SECRET || '',
      clientKey: process.env.MASTODON_CLIENT_KEY || '',
      accessToken: process.env.MASTODON_ACCESS_TOKEN || '',
      instance: 'https://mastodon.social', // Default instance
    } as MastodonCredentials,
    rateLimits: {
      postStatus: 300, // 300 requests per 5-minute window (typical)
    },
  },

  // LinkedIn API configuration
  linkedin: {
    credentials: {
      clientId: process.env.LINKEDIN_CLIENT_ID || '',
      clientSecret: process.env.LINKEDIN_CLIENT_SECRET || '',
      accessToken: process.env.LINKEDIN_ACCESS_TOKEN || '',
      refreshToken: process.env.LINKEDIN_REFRESH_TOKEN || '',
    } as LinkedInCredentials,
    rateLimits: {
      postShare: 100, // LinkedIn has various rate limits depending on the API
      companyUpdates: 50,
    },
    debug: true, // Enable debug mode for LinkedIn
  },

  // AI services configuration
  ai: {
    openai: {
      apiKey: process.env.OPENAI_API_KEY || '',
      model: 'gpt-4o',
    },
    anthropic: {
      apiKey: process.env.ANTHROPIC_API_KEY || '',
      model: 'claude-3-opus-20240229',
    },
    deepseek: {
      apiKey: process.env.DEEPSEEK_API_KEY || '',
    },
    grok: {
      apiKey: process.env.GROK_API_KEY || '',
    },
    huggingface: {
      apiKey: process.env.HUGGINGFACE_API_KEY || '',
    },
  },

  // Research services configuration
  research: {
    brave: {
      apiKey: process.env.BRAVE_API_KEY || '',
    },
    google: {
      apiKey: process.env.GOOGLE_API_KEY || '',
    },
  },

  // Rate limiting configuration
  rateLimit: {
    enabled: process.env.RATE_LIMIT_ENABLED === 'true',
    queueSize: 100,
    retryDelay: 1000, // 1 second
    maxRetries: 3,
  },

  // Caching configuration
  cache: {
    enabled: process.env.CACHE_ENABLED === 'true',
    ttl: 3600, // 1 hour
  },
};

// Validate required configuration
const validateConfig = () => {
  const missingVars = [];

  // Check Twitter credentials
  if (!config.twitter.credentials.apiKey) missingVars.push('TWITTER_API_KEY');
  if (!config.twitter.credentials.apiSecret) missingVars.push('TWITTER_API_SECRET');
  if (!config.twitter.credentials.bearerToken) missingVars.push('TWITTER_BEARER_TOKEN');
  if (!config.twitter.credentials.accessToken) missingVars.push('TWITTER_ACCESS_TOKEN');
  if (!config.twitter.credentials.accessSecret) missingVars.push('TWITTER_ACCESS_SECRET');

  // Check Mastodon credentials
  if (!config.mastodon.credentials.clientSecret) missingVars.push('MASTODON_CLIENT_SECRET');
  if (!config.mastodon.credentials.clientKey) missingVars.push('MASTODON_CLIENT_KEY');
  if (!config.mastodon.credentials.accessToken) missingVars.push('MASTODON_ACCESS_TOKEN');

  // Check LinkedIn credentials
  if (!config.linkedin.credentials.clientId) missingVars.push('LINKEDIN_CLIENT_ID');
  if (!config.linkedin.credentials.clientSecret) missingVars.push('LINKEDIN_CLIENT_SECRET');
  if (!config.linkedin.credentials.accessToken) missingVars.push('LINKEDIN_ACCESS_TOKEN');

  // Check at least one AI service
  if (!config.ai.openai.apiKey && !config.ai.anthropic.apiKey) {
    missingVars.push('OPENAI_API_KEY or ANTHROPIC_API_KEY');
  }

  // Check research services
  if (!config.research.brave.apiKey) {
    missingVars.push('BRAVE_API_KEY');
  }

  if (missingVars.length > 0) {
    console.error('[Config] Missing required environment variables:', missingVars.join(', '));
    process.exit(1);
  }
};

// Export configuration
export default config;
export { validateConfig };
