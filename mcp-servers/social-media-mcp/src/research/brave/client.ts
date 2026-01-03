import axios from 'axios';
import config from '../../config/index.js';
import { createComponentLogger } from '../../utils/logger.js';
import rateLimitManager from '../../rate-limit/manager.js';

const logger = createComponentLogger('BraveSearchClient');

/**
 * Brave Search client for searching the web
 */
class BraveSearchClient {
  private readonly apiKey: string;
  private readonly baseUrl: string = 'https://api.search.brave.com/res/v1';

  constructor() {
    this.apiKey = config.research.brave.apiKey;
    
    if (!this.apiKey) {
      logger.error('Brave Search API key not found');
      throw new Error('Brave Search API key not found');
    }
    
    logger.info('Brave Search client initialized');
  }

  /**
   * Search the web
   */
  async search(query: string, count: number = 10): Promise<any> {
    logger.info('Searching the web', { query, count });

    try {
      // Use rate limit manager to handle API rate limits
      const result = await rateLimitManager.executeRequest({
        api: 'brave',
        endpoint: 'search',
        method: 'GET',
        priority: 'high',
        retryCount: 0,
        maxRetries: config.rateLimit.maxRetries,
        execute: async () => {
          // Make request to Brave Search API
          const response = await axios.get(`${this.baseUrl}/search`, {
            headers: {
              'Accept': 'application/json',
              'Accept-Encoding': 'gzip',
              'X-Subscription-Token': this.apiKey,
            },
            params: {
              q: query,
              count: count,
              search_lang: 'en',
              country: 'US',
              spellcheck: true,
              freshness: 'month', // Get results from the last month
            },
          });
          
          return response.data;
        }
      });

      logger.info('Search results retrieved successfully', { 
        query, 
        resultCount: result.web?.results?.length || 0 
      });
      
      return this.formatSearchResults(result);
    } catch (error) {
      logger.error('Error searching the web', { 
        query,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Format search results
   */
  private formatSearchResults(data: any): any {
    // Extract web results
    const webResults = data.web?.results || [];
    
    // Extract news results
    const newsResults = data.news?.results || [];
    
    // Extract discussions (forum posts, etc.)
    const discussionResults = data.discussions?.results || [];
    
    // Format web results
    const formattedWebResults = webResults.map((result: any) => ({
      title: result.title,
      url: result.url,
      description: result.description,
      source: new URL(result.url).hostname,
    }));
    
    // Format news results
    const formattedNewsResults = newsResults.map((result: any) => ({
      title: result.title,
      url: result.url,
      description: result.description,
      source: result.source,
      publishedAt: result.published_timestamp,
    }));
    
    // Format discussion results
    const formattedDiscussionResults = discussionResults.map((result: any) => ({
      title: result.title,
      url: result.url,
      description: result.description,
      source: result.source,
    }));
    
    return {
      query: data.query?.query || '',
      web: formattedWebResults,
      news: formattedNewsResults,
      discussions: formattedDiscussionResults,
      source: {
        name: 'Brave Search',
        type: 'search',
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Extract hashtags from search results
   */
  async extractHashtags(query: string, count: number = 5): Promise<string[]> {
    logger.info('Extracting hashtags', { query, count });

    try {
      // Search for the query
      const searchResults = await this.search(query, 10);
      
      // Extract keywords from titles and descriptions
      const keywords = this.extractKeywords(searchResults);
      
      // Convert keywords to hashtags
      const hashtags = keywords
        .map(keyword => `#${keyword.replace(/\s+/g, '')}`)
        .slice(0, count);
      
      logger.info('Hashtags extracted successfully', { count: hashtags.length });
      
      return hashtags;
    } catch (error) {
      logger.error('Error extracting hashtags', { 
        query,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Extract keywords from search results
   */
  private extractKeywords(searchResults: any): string[] {
    // Combine titles and descriptions from all result types
    const texts: string[] = [];
    
    // Add web results
    searchResults.web.forEach((result: any) => {
      texts.push(result.title);
      texts.push(result.description);
    });
    
    // Add news results
    searchResults.news.forEach((result: any) => {
      texts.push(result.title);
      texts.push(result.description);
    });
    
    // Add discussion results
    searchResults.discussions.forEach((result: any) => {
      texts.push(result.title);
      texts.push(result.description);
    });
    
    // Join all texts
    const text = texts.join(' ');
    
    // Extract keywords (simple implementation)
    // In a real implementation, you would use NLP techniques
    const words = text.toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/)
      .filter(word => word.length > 3)
      .filter(word => !this.isStopWord(word));
    
    // Count word frequency
    const wordCounts: Record<string, number> = {};
    words.forEach(word => {
      wordCounts[word] = (wordCounts[word] || 0) + 1;
    });
    
    // Sort by frequency
    const sortedWords = Object.entries(wordCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([word]) => word);
    
    return sortedWords;
  }

  /**
   * Check if a word is a stop word
   */
  private isStopWord(word: string): boolean {
    const stopWords = [
      'the', 'and', 'that', 'have', 'for', 'not', 'with', 'you', 'this', 'but',
      'his', 'from', 'they', 'she', 'will', 'would', 'there', 'their', 'what',
      'about', 'which', 'when', 'make', 'like', 'time', 'just', 'know', 'take',
      'people', 'year', 'your', 'good', 'some', 'could', 'them', 'than', 'then',
      'now', 'look', 'only', 'come', 'over', 'think', 'also', 'back', 'after',
      'use', 'two', 'how', 'our', 'work', 'first', 'well', 'way', 'even', 'new',
      'want', 'because', 'any', 'these', 'give', 'day', 'most', 'cant', 'cant',
    ];
    
    return stopWords.includes(word);
  }
}

// Export singleton instance
export default new BraveSearchClient();
