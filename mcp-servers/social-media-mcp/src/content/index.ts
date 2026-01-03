import { createComponentLogger } from '../utils/logger.js';
import { UserIntent, Content, ResearchData, SocialPlatform } from '../types/index.js';
import { ContentGenerationStrategy } from './strategies/interface.js';
import openaiStrategy from './strategies/openai.js';
import anthropicStrategy from './strategies/anthropic.js';

const logger = createComponentLogger('ContentGenerator');

/**
 * Content generator for creating content for social media platforms
 */
class ContentGenerator {
  private strategies: ContentGenerationStrategy[] = [];
  
  constructor() {
    // Register strategies
    this.registerStrategy(anthropicStrategy);
    this.registerStrategy(openaiStrategy);
    
    // Log available strategies
    const availableStrategies = this.strategies
      .filter(strategy => strategy.isAvailable())
      .map(strategy => strategy.getName());
    
    logger.info('Content generator initialized', { 
      availableStrategies,
      strategyCount: availableStrategies.length,
    });
    
    if (availableStrategies.length === 0) {
      logger.warn('No content generation strategies available');
    }
  }
  
  /**
   * Register a content generation strategy
   */
  registerStrategy(strategy: ContentGenerationStrategy): void {
    this.strategies.push(strategy);
    
    // Sort strategies by priority (highest first)
    this.strategies.sort((a, b) => b.getPriority() - a.getPriority());
    
    logger.info('Strategy registered', { 
      name: strategy.getName(),
      available: strategy.isAvailable(),
      priority: strategy.getPriority(),
    });
  }
  
  /**
   * Generate content for a platform
   */
  async generateContent(
    intent: UserIntent,
    research: ResearchData,
    platform: SocialPlatform
  ): Promise<Content> {
    logger.info('Generating content', { 
      platform,
      contentType: intent.contentType || 'general',
    });
    
    // Get available strategies
    const availableStrategies = this.strategies.filter(strategy => strategy.isAvailable());
    
    if (availableStrategies.length === 0) {
      logger.error('No content generation strategies available');
      throw new Error('No content generation strategies available');
    }
    
    // Try strategies in order of priority
    let lastError: Error | null = null;
    
    for (const strategy of availableStrategies) {
      try {
        logger.info('Trying strategy', { name: strategy.getName() });
        
        const content = await strategy.generateContent(intent, research, platform);
        
        logger.info('Content generated successfully', { 
          strategy: strategy.getName(),
          platform,
          textLength: content.text.length,
        });
        
        return content;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        
        logger.warn('Strategy failed', { 
          name: strategy.getName(),
          error: lastError.message,
        });
        
        // Continue with next strategy
      }
    }
    
    // If all strategies failed, throw the last error
    logger.error('All content generation strategies failed');
    throw lastError || new Error('All content generation strategies failed');
  }
  
  /**
   * Generate content for multiple platforms
   */
  async generateContentForPlatforms(
    intent: UserIntent,
    research: ResearchData,
    platforms: SocialPlatform[]
  ): Promise<Record<SocialPlatform, Content>> {
    logger.info('Generating content for multiple platforms', { 
      platforms,
      contentType: intent.contentType || 'general',
    });
    
    const result: Record<SocialPlatform, Content> = {} as Record<SocialPlatform, Content>;
    
    // Generate content for each platform
    for (const platform of platforms) {
      try {
        result[platform] = await this.generateContent(intent, research, platform);
      } catch (error) {
        logger.error('Error generating content for platform', { 
          platform,
          error: error instanceof Error ? error.message : String(error),
        });
        
        // Create placeholder content for failed platforms
        result[platform] = {
          text: `Failed to generate content for ${platform}: ${error instanceof Error ? error.message : String(error)}`,
          platform,
          hashtags: [],
        };
      }
    }
    
    return result;
  }
}

// Export singleton instance
export default new ContentGenerator();
