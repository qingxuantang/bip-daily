// Type definitions for the Social Media MCP Server

// User intent from natural language input
export interface UserIntent {
  rawInput: string;
  topic: string;
  tone?: string;
  contentType?: ContentType;
  platforms: SocialPlatform[];
  mediaRequirements?: MediaRequirement;
  researchRequirements?: ResearchRequirement;
  schedulingRequirements?: SchedulingRequirement;
  
  // Additional properties for enhanced user experience
  audience?: string;
  goal?: string;
  actionableInsights?: string;
  technicalLevel?: string;
  examples?: string;
  focus?: string;
  
  // Conversation tracking
  conversationId?: string;
}

// Content types
export enum ContentType {
  ANNOUNCEMENT = 'announcement',
  NEWS = 'news',
  PROMOTION = 'promotion',
  ENGAGEMENT = 'engagement',
  EDUCATIONAL = 'educational',
  ENTERTAINMENT = 'entertainment',
  THREAD = 'thread',
}

// Social media platforms
export enum SocialPlatform {
  TWITTER = 'twitter',
  MASTODON = 'mastodon',
  LINKEDIN = 'linkedin',
}

// Media requirements
export interface MediaRequirement {
  includeImage?: boolean;
  includeVideo?: boolean;
  imageDescription?: string;
  imageCount?: number;
}

// Research requirements
export interface ResearchRequirement {
  includeHashtags?: boolean;
  includeFacts?: boolean;
  includeTrends?: boolean;
  includeNews?: boolean;
  specificSources?: string[];
}

// Scheduling requirements
export interface SchedulingRequirement {
  postImmediately?: boolean;
  scheduledTime?: Date;
  useOptimalTime?: boolean;
}

// Research data from various sources
export interface ResearchData {
  hashtags?: string[];
  facts?: string[];
  trends?: TrendData[];
  news?: NewsData[];
  sources: ResearchSource[];
}

// Trend data
export interface TrendData {
  name: string;
  volume?: number;
  category?: string;
  region?: string;
}

// News data
export interface NewsData {
  title: string;
  url: string;
  source: string;
  summary: string;
  publishedAt: Date;
}

// Research source
export interface ResearchSource {
  name: string;
  type: 'search' | 'ai' | 'api';
  url?: string;
  timestamp: Date;
}

// Generated content
export interface Content {
  text: string;
  platform: SocialPlatform;
  media?: MediaContent[];
  hashtags?: string[];
  thread?: string[];
  engagementQuestion?: string;

  // Additional properties for LinkedIn and other platforms
  url?: string;                // URL for article shares
  title?: string;              // Title for article shares
  description?: string;        // Description for article shares

  // Twitter thread support
  replyToTweetId?: string;     // Tweet ID to reply to (for thread posting)
}

// Media content
export interface MediaContent {
  type: 'image' | 'video' | 'gif';
  url?: string;
  altText?: string;
  data?: Buffer;
}

// Post result
export interface PostResult {
  platform: SocialPlatform;
  success: boolean;
  postId?: string;
  url?: string;
  error?: string;
  timestamp: Date;
  isMock?: boolean; // Indicates if this is a mock response
}

// Engagement metrics
export interface EngagementMetrics {
  platform: SocialPlatform;
  postId: string;
  likes: number;
  shares: number;
  comments: number;
  views?: number;
  engagementRate: number;
  timestamp: Date;
  isMock?: boolean; // Indicates if this is a mock response
}

// Performance data
export interface PerformanceData {
  platform: SocialPlatform;
  contentType: ContentType;
  postTime: Date;
  engagementRate: number;
  metrics: EngagementMetrics;
}

// API credentials
export interface TwitterCredentials {
  apiKey: string;
  apiSecret: string;
  bearerToken: string;
  accessToken: string;
  accessSecret: string;
  oauthClient: string;
  clientSecret: string;
}

export interface MastodonCredentials {
  clientSecret: string;
  clientKey: string;
  accessToken: string;
  instance?: string;
}

export interface LinkedInCredentials {
  clientId: string;
  clientSecret: string;
  accessToken: string;
  refreshToken?: string;
}

// Rate limit information
export interface RateLimitInfo {
  api: string;
  endpoint: string;
  limit: number;
  remaining: number;
  reset: Date;
}

// API request
export interface ApiRequest {
  api: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  priority: 'high' | 'medium' | 'low';
  retryCount: number;
  maxRetries: number;
  execute: () => Promise<any>;
}
