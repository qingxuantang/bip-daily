import { RateLimitInfo, ApiRequest } from '../types/index.js';
import { createComponentLogger } from '../utils/logger.js';
import config from '../config/index.js';

const logger = createComponentLogger('RateLimitManager');

/**
 * Token bucket implementation for rate limiting
 */
class TokenBucket {
  private tokens: number;
  private lastRefill: number;
  private readonly capacity: number;
  private readonly refillRate: number; // tokens per millisecond

  constructor(capacity: number, refillTimeMs: number) {
    this.capacity = capacity;
    this.tokens = capacity;
    this.lastRefill = Date.now();
    this.refillRate = capacity / refillTimeMs;
  }

  /**
   * Refill tokens based on elapsed time
   */
  private refill(): void {
    const now = Date.now();
    const elapsed = now - this.lastRefill;
    const tokensToAdd = elapsed * this.refillRate;
    
    if (tokensToAdd > 0) {
      this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
      this.lastRefill = now;
    }
  }

  /**
   * Check if tokens can be consumed
   */
  canConsume(count: number = 1): boolean {
    this.refill();
    return this.tokens >= count;
  }

  /**
   * Consume tokens
   */
  consume(count: number = 1): boolean {
    this.refill();
    if (this.tokens >= count) {
      this.tokens -= count;
      return true;
    }
    return false;
  }

  /**
   * Get time until next token is available
   */
  getWaitTimeMs(count: number = 1): number {
    this.refill();
    if (this.tokens >= count) return 0;
    
    const tokensNeeded = count - this.tokens;
    return Math.ceil(tokensNeeded / this.refillRate);
  }
}

/**
 * Priority queue for API requests
 */
class PriorityQueue<T extends ApiRequest> {
  private readonly queues: {
    high: T[];
    medium: T[];
    low: T[];
  };
  private readonly maxSize: number;

  constructor(maxSize: number = 100) {
    this.queues = {
      high: [],
      medium: [],
      low: [],
    };
    this.maxSize = maxSize;
  }

  /**
   * Enqueue a request with priority
   */
  enqueue(request: T): boolean {
    const queue = this.queues[request.priority];
    
    if (this.size() >= this.maxSize) {
      logger.warn('Queue is full, dropping request', { api: request.api, endpoint: request.endpoint });
      return false;
    }
    
    queue.push(request);
    logger.debug('Request enqueued', { 
      api: request.api, 
      endpoint: request.endpoint, 
      priority: request.priority,
      queueSize: this.size()
    });
    return true;
  }

  /**
   * Dequeue the highest priority request
   */
  dequeue(): T | undefined {
    if (this.queues.high.length > 0) return this.queues.high.shift();
    if (this.queues.medium.length > 0) return this.queues.medium.shift();
    if (this.queues.low.length > 0) return this.queues.low.shift();
    return undefined;
  }

  /**
   * Get the total size of all queues
   */
  size(): number {
    return this.queues.high.length + this.queues.medium.length + this.queues.low.length;
  }

  /**
   * Check if all queues are empty
   */
  isEmpty(): boolean {
    return this.size() === 0;
  }
}

/**
 * Rate limit manager for handling API rate limits
 */
class RateLimitManager {
  private readonly buckets: Map<string, TokenBucket> = new Map();
  private readonly rateLimits: Map<string, RateLimitInfo> = new Map();
  private readonly requestQueue: PriorityQueue<ApiRequest>;
  private processing: boolean = false;
  private readonly enabled: boolean;

  constructor() {
    this.enabled = config.rateLimit.enabled;
    this.requestQueue = new PriorityQueue<ApiRequest>(config.rateLimit.queueSize);
    
    // Initialize token buckets for known APIs
    this.initializeBuckets();
    
    logger.info('Rate limit manager initialized', { enabled: this.enabled });
  }

  /**
   * Initialize token buckets for known APIs
   */
  private initializeBuckets(): void {
    // Twitter rate limits
    this.buckets.set('twitter:postTweet', new TokenBucket(
      config.twitter.rateLimits.postTweet,
      15 * 60 * 1000 // 15 minutes
    ));
    
    this.buckets.set('twitter:timeline', new TokenBucket(
      config.twitter.rateLimits.timeline,
      15 * 60 * 1000 // 15 minutes
    ));
    
    // Mastodon rate limits
    this.buckets.set('mastodon:postStatus', new TokenBucket(
      config.mastodon.rateLimits.postStatus,
      5 * 60 * 1000 // 5 minutes
    ));
    
    // AI service rate limits (example values)
    this.buckets.set('openai:completion', new TokenBucket(
      60, // 60 requests per minute
      60 * 1000
    ));
    
    this.buckets.set('anthropic:completion', new TokenBucket(
      60, // 60 requests per minute
      60 * 1000
    ));
    
    // Research service rate limits
    this.buckets.set('brave:search', new TokenBucket(
      60, // 60 requests per minute
      60 * 1000
    ));
  }

  /**
   * Update rate limit information from API response
   */
  updateRateLimit(info: RateLimitInfo): void {
    const key = `${info.api}:${info.endpoint}`;
    this.rateLimits.set(key, info);
    
    logger.debug('Rate limit updated', { 
      api: info.api, 
      endpoint: info.endpoint, 
      remaining: info.remaining, 
      limit: info.limit,
      reset: info.reset
    });
  }

  /**
   * Check if a request can be executed
   */
  canExecute(api: string, endpoint: string, cost: number = 1): boolean {
    if (!this.enabled) return true;
    
    const key = `${api}:${endpoint}`;
    const bucket = this.buckets.get(key);
    
    if (!bucket) {
      logger.warn('No rate limit bucket found for API', { api, endpoint });
      return true;
    }
    
    return bucket.canConsume(cost);
  }

  /**
   * Execute a request directly if possible, or queue it
   */
  async executeRequest(request: ApiRequest): Promise<any> {
    if (!this.enabled) {
      return request.execute();
    }
    
    const key = `${request.api}:${request.endpoint}`;
    const bucket = this.buckets.get(key);
    
    if (!bucket) {
      logger.warn('No rate limit bucket found for API', { 
        api: request.api, 
        endpoint: request.endpoint 
      });
      return request.execute();
    }
    
    if (bucket.canConsume(1)) {
      bucket.consume(1);
      try {
        return await request.execute();
      } catch (error) {
        // Check if error is due to rate limiting
        if (this.isRateLimitError(error)) {
          logger.warn('Rate limit exceeded, queuing request', { 
            api: request.api, 
            endpoint: request.endpoint 
          });
          this.requestQueue.enqueue(request);
          this.processQueue();
          throw new Error(`Rate limit exceeded for ${request.api}:${request.endpoint}`);
        }
        throw error;
      }
    } else {
      const waitTime = bucket.getWaitTimeMs(1);
      logger.info('Rate limit reached, queuing request', { 
        api: request.api, 
        endpoint: request.endpoint, 
        waitTime 
      });
      
      this.requestQueue.enqueue(request);
      this.processQueue();
      
      throw new Error(`Rate limit reached for ${request.api}:${request.endpoint}, request queued`);
    }
  }

  /**
   * Process the request queue
   */
  private async processQueue(): Promise<void> {
    if (this.processing || this.requestQueue.isEmpty()) return;
    
    this.processing = true;
    
    try {
      while (!this.requestQueue.isEmpty()) {
        const request = this.requestQueue.dequeue();
        if (!request) break;
        
        const key = `${request.api}:${request.endpoint}`;
        const bucket = this.buckets.get(key);
        
        if (!bucket) {
          logger.warn('No rate limit bucket found for queued request', { 
            api: request.api, 
            endpoint: request.endpoint 
          });
          continue;
        }
        
        if (bucket.canConsume(1)) {
          bucket.consume(1);
          try {
            await request.execute();
            logger.debug('Queued request executed successfully', { 
              api: request.api, 
              endpoint: request.endpoint 
            });
          } catch (error) {
            if (this.isRateLimitError(error) && request.retryCount < request.maxRetries) {
              // Increment retry count and requeue
              request.retryCount++;
              this.requestQueue.enqueue(request);
              logger.warn('Rate limit error for queued request, requeuing', { 
                api: request.api, 
                endpoint: request.endpoint,
                retryCount: request.retryCount
              });
              
              // Wait before processing more requests
              await new Promise(resolve => setTimeout(resolve, config.rateLimit.retryDelay));
            } else {
              logger.error('Error executing queued request', { 
                api: request.api, 
                endpoint: request.endpoint,
                error: error instanceof Error ? error.message : String(error)
              });
            }
          }
        } else {
          // Put the request back in the queue
          this.requestQueue.enqueue(request);
          
          // Wait before checking again
          const waitTime = bucket.getWaitTimeMs(1);
          logger.debug('Waiting for rate limit to reset', { 
            api: request.api, 
            endpoint: request.endpoint,
            waitTime
          });
          
          await new Promise(resolve => setTimeout(resolve, waitTime));
        }
      }
    } finally {
      this.processing = false;
    }
  }

  /**
   * Check if an error is due to rate limiting
   */
  private isRateLimitError(error: any): boolean {
    if (!error) return false;
    
    // Check for common rate limit status codes
    if (error.status === 429 || error.statusCode === 429) return true;
    
    // Check for rate limit messages
    const message = error.message || '';
    return message.includes('rate limit') || 
           message.includes('too many requests') ||
           message.includes('exceeded');
  }
}

// Export singleton instance
export default new RateLimitManager();
