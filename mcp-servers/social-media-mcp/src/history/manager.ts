import fs from 'fs';
import path from 'path';
import { createComponentLogger } from '../utils/logger.js';
import { Content, SocialPlatform } from '../types/index.js';
import crypto from 'crypto';

const logger = createComponentLogger('HistoryManager');

/**
 * Post history entry
 */
export interface PostHistoryEntry {
  id: string;
  timestamp: string;
  topic: string;
  keywords: string[];
  platforms: SocialPlatform[];
  content: Record<SocialPlatform, string>;
  instruction: string;
}

/**
 * Post history data
 */
export interface PostHistoryData {
  posts: PostHistoryEntry[];
}

/**
 * History manager for storing and retrieving post history
 */
class HistoryManager {
  private readonly historyDir: string;
  private readonly historyFile: string;
  private history: PostHistoryData;

  constructor() {
    // Create history directory if it doesn't exist
    this.historyDir = path.join(process.cwd(), 'data', 'history');
    this.historyFile = path.join(this.historyDir, 'posts.json');
    
    // Ensure directory exists
    if (!fs.existsSync(this.historyDir)) {
      fs.mkdirSync(this.historyDir, { recursive: true });
      logger.info('Created history directory', { dir: this.historyDir });
    }
    
    // Load history or create empty history
    this.history = this.loadHistory();
    
    logger.info('History manager initialized', { 
      historyFile: this.historyFile,
      postCount: this.history.posts.length,
    });
  }

  /**
   * Load history from file
   */
  private loadHistory(): PostHistoryData {
    try {
      if (fs.existsSync(this.historyFile)) {
        const data = fs.readFileSync(this.historyFile, 'utf-8');
        return JSON.parse(data);
      }
    } catch (error) {
      logger.error('Error loading history', { 
        error: error instanceof Error ? error.message : String(error) 
      });
    }
    
    // Return empty history if file doesn't exist or there's an error
    return { posts: [] };
  }

  /**
   * Save history to file
   */
  private saveHistory(): void {
    try {
      fs.writeFileSync(this.historyFile, JSON.stringify(this.history, null, 2), 'utf-8');
      logger.info('History saved', { postCount: this.history.posts.length });
    } catch (error) {
      logger.error('Error saving history', { 
        error: error instanceof Error ? error.message : String(error) 
      });
    }
  }

  /**
   * Add a post to history
   */
  addToHistory(
    topic: string,
    instruction: string,
    platforms: SocialPlatform[],
    content: Record<SocialPlatform, Content>,
    keywords: string[] = []
  ): string {
    // Generate a unique ID for the post
    const id = crypto.randomUUID();
    
    // Create a new history entry with default empty content for all platforms
    const entry: PostHistoryEntry = {
      id,
      timestamp: new Date().toISOString(),
      topic,
      keywords,
      platforms,
      content: {
        [SocialPlatform.TWITTER]: '',
        [SocialPlatform.MASTODON]: '',
        [SocialPlatform.LINKEDIN]: '',
      },
      instruction,
    };
    
    // Add content for each platform
    for (const platform of platforms) {
      if (content[platform]) {
        entry.content[platform] = content[platform].text;
      }
    }
    
    // Add to history
    this.history.posts.push(entry);
    
    // Save history
    this.saveHistory();
    
    logger.info('Post added to history', { id, topic });
    
    return id;
  }

  /**
   * Get all posts from history
   */
  getHistory(): PostHistoryEntry[] {
    return this.history.posts;
  }

  /**
   * Search history for posts with similar topics
   */
  searchHistory(topic: string, threshold: number = 0.7): PostHistoryEntry[] {
    logger.info('Searching history', { topic, threshold });
    
    const results = this.history.posts
      .map(post => ({
        post,
        similarity: this.calculateSimilarity(topic, post.topic),
      }))
      .filter(result => result.similarity >= threshold)
      .sort((a, b) => b.similarity - a.similarity)
      .map(result => result.post);
    
    logger.info('Search results', { count: results.length });
    
    return results;
  }

  /**
   * Calculate similarity between two topics
   * This is a simple implementation using Jaccard similarity
   * In a real implementation, you would use a more sophisticated approach
   */
  calculateSimilarity(topic1: string, topic2: string): number {
    // Convert to lowercase and split into words
    const words1 = new Set(topic1.toLowerCase().split(/\s+/));
    const words2 = new Set(topic2.toLowerCase().split(/\s+/));
    
    // Calculate intersection
    const intersection = new Set([...words1].filter(word => words2.has(word)));
    
    // Calculate union
    const union = new Set([...words1, ...words2]);
    
    // Calculate Jaccard similarity
    return intersection.size / union.size;
  }

  /**
   * Check if a topic is similar to any existing posts
   */
  isSimilarToExisting(topic: string, threshold: number = 0.7): boolean {
    const similarPosts = this.searchHistory(topic, threshold);
    return similarPosts.length > 0;
  }

  /**
   * Get similar posts for a topic
   */
  getSimilarPosts(topic: string, threshold: number = 0.7): PostHistoryEntry[] {
    return this.searchHistory(topic, threshold);
  }

  /**
   * Delete a post from history
   */
  deletePost(id: string): boolean {
    const initialLength = this.history.posts.length;
    this.history.posts = this.history.posts.filter(post => post.id !== id);
    
    if (this.history.posts.length < initialLength) {
      this.saveHistory();
      logger.info('Post deleted from history', { id });
      return true;
    }
    
    logger.warn('Post not found in history', { id });
    return false;
  }

  /**
   * Clear all history
   */
  clearHistory(): void {
    this.history = { posts: [] };
    this.saveHistory();
    logger.info('History cleared');
  }
}

// Export singleton instance
export default new HistoryManager();
