import { createComponentLogger } from '../../utils/logger.js';
import rateLimitManager from '../../rate-limit/manager.js';

const logger = createComponentLogger('BraveSearchMcpClient');

/**
 * Brave Search MCP client for searching the web using the Brave Search MCP server
 */
class BraveSearchMcpClient {
  private readonly serverName = 'github.com/modelcontextprotocol/servers/tree/main/src/brave-search';

  constructor() {
    logger.info('Brave Search MCP client initialized');
  }

  /**
   * Search the web using the Brave Search MCP
   */
  async search(query: string, count: number = 10): Promise<any> {
    logger.info('Searching the web using Brave Search MCP', { query, count });

    try {
      // Use rate limit manager to handle API rate limits
      const result = await rateLimitManager.executeRequest({
        api: 'brave',
        endpoint: 'search',
        method: 'GET',
        priority: 'high',
        retryCount: 0,
        maxRetries: 3,
        execute: async () => {
          // Use the MCP tool to search
          const response = await this.useMcpTool('brave_web_search', {
            query,
            count
          });
          
          return response;
        }
      });

      logger.info('Search results retrieved successfully', { 
        query, 
        resultCount: result.results?.length || 0 
      });
      
      return this.formatSearchResults(result, query);
    } catch (error) {
      logger.error('Error searching the web', { 
        query,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Format search results from the Brave Search MCP
   */
  private formatSearchResults(data: any, query: string): any {
    // Extract web results
    const webResults = data.results || [];
    
    // Format web results
    const formattedWebResults = webResults.map((result: any) => ({
      title: result.title,
      url: result.url,
      description: result.description,
      source: new URL(result.url).hostname,
    }));
    
    return {
      query: query,
      web: formattedWebResults,
      news: [], // Brave Search MCP doesn't separate news results
      discussions: [], // Brave Search MCP doesn't separate discussion results
      source: {
        name: 'Brave Search MCP',
        type: 'search',
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Extract hashtags from search results
   */
  async extractHashtags(query: string, count: number = 5): Promise<string[]> {
    logger.info('Extracting hashtags using Brave Search MCP', { query, count });

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

  /**
   * Use the MCP tool to communicate with the Brave Search MCP server
   */
  private async useMcpTool(toolName: string, args: any): Promise<any> {
    try {
      // @ts-ignore - This is a special function provided by the MCP environment
      const result = await use_mcp_tool({
        server_name: this.serverName,
        tool_name: toolName,
        arguments: args
      });
      
      return result;
    } catch (error) {
      logger.error('Error using MCP tool', {
        toolName,
        args,
        error: error instanceof Error ? error.message : String(error)
      });
      
      throw error;
    }
  }
}

// Export singleton instance
export default new BraveSearchMcpClient();
