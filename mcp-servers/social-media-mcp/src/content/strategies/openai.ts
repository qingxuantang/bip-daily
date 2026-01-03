import axios from 'axios';
import config from '../../config/index.js';
import { createComponentLogger } from '../../utils/logger.js';
import rateLimitManager from '../../rate-limit/manager.js';
import { ContentGenerationStrategy } from './interface.js';
import { UserIntent, Content, ResearchData, SocialPlatform, ContentType } from '../../types/index.js';

const logger = createComponentLogger('OpenAIStrategy');

/**
 * OpenAI content generation strategy
 * 
 * This strategy uses the OpenAI API to generate content.
 */
export class OpenAIStrategy implements ContentGenerationStrategy {
  private readonly apiKey: string;
  private readonly model: string;
  private readonly baseUrl: string = 'https://api.openai.com/v1';
  
  constructor() {
    this.apiKey = config.ai.openai.apiKey;
    this.model = config.ai.openai.model;
    
    logger.info('OpenAI strategy initialized', { model: this.model });
  }
  
  /**
   * Get the name of the strategy
   */
  getName(): string {
    return 'OpenAI';
  }
  
  /**
   * Check if the strategy is available
   */
  isAvailable(): boolean {
    return !!this.apiKey;
  }
  
  /**
   * Get the priority of the strategy
   */
  getPriority(): number {
    return 2; // Medium priority
  }
  
  /**
   * Generate content based on user intent and research data
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
    
    try {
      // Use rate limit manager to handle API rate limits
      const result = await rateLimitManager.executeRequest({
        api: 'openai',
        endpoint: 'completion',
        method: 'POST',
        priority: 'high',
        retryCount: 0,
        maxRetries: config.rateLimit.maxRetries,
        execute: async () => {
          // Create prompt based on intent and research data
          const prompt = this.createPrompt(intent, research, platform);
          
          // Make request to OpenAI API
          const response = await axios.post(
            `${this.baseUrl}/chat/completions`,
            {
              model: this.model,
              messages: [
                {
                  role: 'system',
                  content: this.getSystemPrompt(platform, intent.contentType),
                },
                {
                  role: 'user',
                  content: prompt,
                },
              ],
              temperature: 0.7,
              max_tokens: this.getMaxTokens(platform),
            },
            {
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.apiKey}`,
              },
            }
          );
          
          return response.data;
        }
      });
      
      // Extract content from response
      const generatedText = result.choices[0].message.content.trim();
      
      // Extract hashtags if present
      const hashtags = this.extractHashtags(generatedText);
      
      // Remove hashtags from text if they're at the end
      let text = generatedText;
      if (hashtags.length > 0) {
        // Check if hashtags are at the end of the text
        const hashtagsText = hashtags.join(' ');
        if (text.endsWith(hashtagsText)) {
          text = text.substring(0, text.length - hashtagsText.length).trim();
        }
      }
      
      logger.info('Content generated successfully', { 
        platform,
        textLength: text.length,
        hashtagCount: hashtags.length,
      });
      
      return {
        text,
        platform,
        hashtags,
      };
    } catch (error) {
      logger.error('Error generating content', { 
        platform,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }
  
  /**
   * Create prompt based on intent and research data
   */
  private createPrompt(
    intent: UserIntent,
    research: ResearchData,
    platform: SocialPlatform
  ): string {
    // Build prompt
    let prompt = `Create a ${platform} post about: ${intent.topic}\n\n`;
    
    // Add tone if specified
    if (intent.tone) {
      prompt += `Tone: ${intent.tone}\n`;
    }
    
    // Add content type if specified
    if (intent.contentType) {
      prompt += `Content type: ${intent.contentType}\n`;
    }
    
    // Add audience if specified
    if (intent.audience) {
      prompt += `Target audience: ${intent.audience}\n`;
    }
    
    // Add goal if specified
    if (intent.goal) {
      prompt += `Goal: ${intent.goal}\n`;
    }
    
    // Add technical level if specified
    if (intent.technicalLevel) {
      prompt += `Technical level: ${intent.technicalLevel}\n`;
    }
    
    // Add research data
    prompt += '\nResearch information:\n';
    
    // Add hashtags
    if (research.hashtags && research.hashtags.length > 0) {
      prompt += `Relevant hashtags: ${research.hashtags.join(', ')}\n`;
    }
    
    // Add facts
    if (research.facts && research.facts.length > 0) {
      prompt += 'Facts:\n';
      research.facts.forEach(fact => {
        prompt += `- ${fact}\n`;
      });
    }
    
    // Add trends
    if (research.trends && research.trends.length > 0) {
      prompt += 'Trending topics:\n';
      research.trends.forEach(trend => {
        prompt += `- ${trend.name} (${trend.volume} mentions)\n`;
      });
    }
    
    // Add news
    if (research.news && research.news.length > 0) {
      prompt += 'Recent news:\n';
      research.news.forEach(news => {
        prompt += `- ${news.title} (${news.source}): ${news.summary}\n`;
      });
    }
    
    // Add actionable insights requirement if specified
    if (intent.actionableInsights) {
      prompt += `\nInclude actionable insights: ${intent.actionableInsights}\n`;
      prompt += 'Make sure to include specific, practical steps that readers can take. Each action should be clear and implementable.\n';
    }
    
    // Add examples if specified
    if (intent.examples) {
      prompt += `\nExamples to reference: ${intent.examples}\n`;
    }
    
    // Add focus if specified
    if (intent.focus) {
      prompt += `\nFocus on: ${intent.focus}\n`;
    }
    
    // Add platform-specific instructions
    if (platform === SocialPlatform.TWITTER) {
      prompt += '\nThis is for Twitter, so keep it under 280 characters. Include 2-3 relevant hashtags at the end.';
      
      // Add call to action for Twitter if actionable insights are requested
      if (intent.actionableInsights) {
        prompt += ' End with a clear call to action.';
      }
    } else if (platform === SocialPlatform.MASTODON) {
      prompt += '\nThis is for Mastodon, so keep it under 500 characters. Include 2-3 relevant hashtags at the end.';
      
      // Add call to action for Mastodon if actionable insights are requested
      if (intent.actionableInsights) {
        prompt += ' End with a clear call to action.';
      }
    }
    
    return prompt;
  }
  
  /**
   * Get system prompt based on platform and content type
   */
  private getSystemPrompt(platform: SocialPlatform, contentType?: ContentType): string {
    let systemPrompt = 'You are a professional social media content creator. ';
    
    // Add platform-specific instructions
    if (platform === SocialPlatform.TWITTER) {
      systemPrompt += 'You create engaging Twitter posts that are concise and impactful. ';
    } else if (platform === SocialPlatform.MASTODON) {
      systemPrompt += 'You create thoughtful Mastodon posts that provide value to the community. ';
    }
    
    // Add content type-specific instructions
    if (contentType) {
      switch (contentType) {
        case ContentType.ANNOUNCEMENT:
          systemPrompt += 'You specialize in creating announcement posts that generate excitement and interest.';
          break;
        case ContentType.NEWS:
          systemPrompt += 'You specialize in creating news posts that are informative and objective.';
          break;
        case ContentType.PROMOTION:
          systemPrompt += 'You specialize in creating promotional posts that drive engagement and conversions.';
          break;
        case ContentType.ENGAGEMENT:
          systemPrompt += 'You specialize in creating engagement posts that spark conversation and interaction.';
          break;
        case ContentType.EDUCATIONAL:
          systemPrompt += 'You specialize in creating educational posts that teach and inform.';
          break;
        case ContentType.ENTERTAINMENT:
          systemPrompt += 'You specialize in creating entertainment posts that are fun and engaging.';
          break;
        case ContentType.THREAD:
          systemPrompt += 'You specialize in creating thread-style posts that tell a compelling story.';
          break;
      }
    }
    
    return systemPrompt;
  }
  
  /**
   * Get max tokens based on platform
   */
  private getMaxTokens(platform: SocialPlatform): number {
    if (platform === SocialPlatform.TWITTER) {
      return 100; // Approximately 280 characters
    } else if (platform === SocialPlatform.MASTODON) {
      return 200; // Approximately 500 characters
    }
    
    return 150; // Default
  }
  
  /**
   * Extract hashtags from text
   */
  private extractHashtags(text: string): string[] {
    const hashtagRegex = /#[a-zA-Z0-9_]+/g;
    const matches = text.match(hashtagRegex);
    
    return matches || [];
  }
}

// Export singleton instance
export default new OpenAIStrategy();
