import { createComponentLogger } from '../../utils/logger.js';
import braveClient from '../brave/mcp-client.js';
import perplexityClient from '../perplexity/mcp-client.js';
import { ResearchData, TrendData, NewsData, ResearchSource } from '../../types/index.js';

const logger = createComponentLogger('ResearchAggregator');

/**
 * Research aggregator for combining results from different research sources
 */
class ResearchAggregator {
  /**
   * Research a topic
   */
  async researchTopic(
    topic: string,
    options: {
      includeHashtags?: boolean;
      includeFacts?: boolean;
      includeTrends?: boolean;
      includeNews?: boolean;
    } = {}
  ): Promise<ResearchData> {
    logger.info('Researching topic', { topic, options });

    const researchData: ResearchData = {
      sources: [],
    };

    try {
      // Get search results from Brave Search
      const searchResults = await braveClient.search(topic, 10);
      
      // Add Brave Search as a source
      researchData.sources.push(searchResults.source);
      
      // Extract hashtags if requested
      if (options.includeHashtags) {
        researchData.hashtags = await braveClient.extractHashtags(topic, 5);
      }
      
      // Extract facts if requested
      if (options.includeFacts) {
        try {
          // Get in-depth research from Perplexity
          const perplexityResults = await perplexityClient.research(topic, { depth: 'detailed' });
          
          // Add Perplexity as a source
          researchData.sources.push(perplexityResults.source);
          
          // Use Perplexity facts if available, otherwise extract from search results
          if (perplexityResults.facts && perplexityResults.facts.length > 0) {
            researchData.facts = perplexityResults.facts;
            logger.info('Using Perplexity facts', { count: perplexityResults.facts.length });
          } else {
            researchData.facts = this.extractFacts(searchResults);
            logger.info('Using extracted facts from search results', { count: researchData.facts.length });
          }
        } catch (error) {
          logger.warn('Error getting Perplexity research, falling back to extracted facts', {
            error: error instanceof Error ? error.message : String(error)
          });
          
          // Fall back to extracting facts from search results
          researchData.facts = this.extractFacts(searchResults);
        }
      }
      
      // Extract news if requested
      if (options.includeNews) {
        researchData.news = this.extractNews(searchResults);
      }
      
      // Get trends if requested
      // Note: In a complete implementation, this would use the Twitter and Mastodon clients
      if (options.includeTrends) {
        researchData.trends = this.generatePlaceholderTrends(topic);
      }
      
      logger.info('Research completed successfully', { 
        topic,
        hashtagCount: researchData.hashtags?.length || 0,
        factCount: researchData.facts?.length || 0,
        newsCount: researchData.news?.length || 0,
        trendCount: researchData.trends?.length || 0,
      });
      
      return researchData;
    } catch (error) {
      logger.error('Error researching topic', { 
        topic,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Extract facts from search results
   */
  private extractFacts(searchResults: any): string[] {
    // In a real implementation, this would use NLP to extract facts
    // For now, we'll use a simple approach
    
    const facts: string[] = [];
    
    // Extract facts from web results
    searchResults.web.forEach((result: any) => {
      const sentences = result.description.split(/[.!?]+/).filter(Boolean);
      
      sentences.forEach((sentence: string) => {
        // Simple heuristic: sentences with numbers or specific keywords might be facts
        if (
          /\d+/.test(sentence) || // Contains numbers
          /according to|research|study|found|shows|reveals|experts|report/i.test(sentence) // Contains fact-like keywords
        ) {
          facts.push(sentence.trim());
        }
      });
    });
    
    // Limit to 5 facts
    return facts.slice(0, 5);
  }

  /**
   * Extract news from search results
   */
  private extractNews(searchResults: any): NewsData[] {
    // Format news results
    return searchResults.news.map((result: any) => ({
      title: result.title,
      url: result.url,
      source: result.source,
      summary: result.description,
      publishedAt: new Date(result.publishedAt || new Date()),
    })).slice(0, 5);
  }

  /**
   * Generate placeholder trends
   * In a real implementation, this would use the Twitter and Mastodon clients
   */
  private generatePlaceholderTrends(topic: string): TrendData[] {
    // Generate some placeholder trends related to the topic
    const keywords = topic.toLowerCase().split(/\s+/);
    
    const trends: TrendData[] = [
      {
        name: `#${keywords[0]}Trends`,
        volume: 10000 + Math.floor(Math.random() * 5000),
        category: 'general',
      },
      {
        name: `#${keywords[keywords.length - 1]}News`,
        volume: 8000 + Math.floor(Math.random() * 4000),
        category: 'news',
      },
      {
        name: `#${keywords.join('')}`,
        volume: 6000 + Math.floor(Math.random() * 3000),
        category: 'technology',
      },
    ];
    
    return trends;
  }
}

// Export singleton instance
export default new ResearchAggregator();
