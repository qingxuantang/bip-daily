import { UserIntent, Content, ResearchData, SocialPlatform } from '../../types/index.js';

/**
 * Content generation strategy interface
 * 
 * This interface defines the contract for content generation strategies.
 * Different AI models can implement this interface to provide content generation capabilities.
 */
export interface ContentGenerationStrategy {
  /**
   * Generate content based on user intent and research data
   * 
   * @param intent User intent from natural language input
   * @param research Research data from various sources
   * @param platform Target social media platform
   * @returns Generated content
   */
  generateContent(
    intent: UserIntent,
    research: ResearchData,
    platform: SocialPlatform
  ): Promise<Content>;
  
  /**
   * Get the name of the strategy
   * 
   * @returns Strategy name
   */
  getName(): string;
  
  /**
   * Check if the strategy is available
   * 
   * @returns True if the strategy is available, false otherwise
   */
  isAvailable(): boolean;
  
  /**
   * Get the priority of the strategy
   * Higher priority strategies are preferred over lower priority ones
   * 
   * @returns Priority value (higher is better)
   */
  getPriority(): number;
}
