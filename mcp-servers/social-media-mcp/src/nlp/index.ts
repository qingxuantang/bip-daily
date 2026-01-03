import { createComponentLogger } from '../utils/logger.js';
import { UserIntent, SocialPlatform, ContentType } from '../types/index.js';
import axios from 'axios';
import config from '../config/index.js';
import rateLimitManager from '../rate-limit/manager.js';
import conversationManager from '../conversation/manager.js';

const logger = createComponentLogger('NLPProcessor');

/**
 * Natural language processor for parsing user intent from natural language instructions
 */
class NLPProcessor {
  /**
   * Parse user intent from natural language instruction
   */
  async parseIntent(instruction: string, conversationId?: string): Promise<UserIntent> {
    logger.info('Parsing intent', { instruction, conversationId });
    
    try {
      // If we have a conversation ID, get the existing intent
      if (conversationId) {
        const conversation = conversationManager.getConversation(conversationId);
        if (conversation) {
          logger.info('Using existing conversation', { conversationId });
          return conversation.intent;
        }
      }
      
      // For now, use a simple rule-based approach
      // In a complete implementation, this would use an AI model
      
      // Check if we have OpenAI API key
      if (config.ai.openai.apiKey) {
        return await this.parseIntentWithOpenAI(instruction);
      }
      
      // Check if we have Anthropic API key
      if (config.ai.anthropic.apiKey) {
        return await this.parseIntentWithAnthropic(instruction);
      }
      
      // Fallback to rule-based parsing
      return this.parseIntentWithRules(instruction);
    } catch (error) {
      logger.error('Error parsing intent', { 
        instruction,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      // Fallback to rule-based parsing
      return this.parseIntentWithRules(instruction);
    }
  }
  
  /**
   * Parse intent with OpenAI
   */
  private async parseIntentWithOpenAI(instruction: string): Promise<UserIntent> {
    logger.info('Parsing intent with OpenAI', { instruction });
    
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
          // Make request to OpenAI API
          const response = await axios.post(
            'https://api.openai.com/v1/chat/completions',
            {
              model: config.ai.openai.model,
              messages: [
                {
                  role: 'system',
                  content: `
                    You are a natural language processing system that extracts structured information from user instructions.
                    Extract the following information from the user's instruction:
                    1. Topic - What the post is about
                    2. Tone (optional) - The tone of the post (e.g., professional, casual, humorous)
                    3. Content Type (optional) - The type of content (announcement, news, promotion, engagement, educational, entertainment, thread)
                    4. Platforms - Which platforms to post to (twitter, mastodon, or all)
                    5. Media Requirements (optional) - Whether to include images or videos
                    6. Research Requirements (optional) - What research to include (hashtags, facts, trends, news)
                    7. Scheduling Requirements (optional) - When to post
                    
                    Respond with a JSON object containing these fields.
                  `,
                },
                {
                  role: 'user',
                  content: instruction,
                },
              ],
              temperature: 0.1,
            },
            {
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.ai.openai.apiKey}`,
              },
            }
          );
          
          return response.data;
        }
      });
      
      // Extract content from response
      const jsonString = result.choices[0].message.content.trim();
      
      // Parse JSON
      const parsedIntent = JSON.parse(jsonString);
      
      // Convert to UserIntent
      const userIntent: UserIntent = {
        rawInput: instruction,
        topic: parsedIntent.topic || instruction,
        tone: parsedIntent.tone,
        contentType: this.parseContentType(parsedIntent.contentType),
        platforms: this.parsePlatforms(parsedIntent.platforms),
        mediaRequirements: parsedIntent.mediaRequirements,
        researchRequirements: parsedIntent.researchRequirements,
        schedulingRequirements: parsedIntent.schedulingRequirements,
      };
      
      logger.info('Intent parsed successfully with OpenAI', { 
        topic: userIntent.topic,
        platforms: userIntent.platforms,
      });
      
      return userIntent;
    } catch (error) {
      logger.error('Error parsing intent with OpenAI', { 
        instruction,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      // Fallback to rule-based parsing
      return this.parseIntentWithRules(instruction);
    }
  }
  
  /**
   * Parse intent with Anthropic
   */
  private async parseIntentWithAnthropic(instruction: string): Promise<UserIntent> {
    logger.info('Parsing intent with Anthropic', { instruction });
    
    try {
      // Use rate limit manager to handle API rate limits
      const result = await rateLimitManager.executeRequest({
        api: 'anthropic',
        endpoint: 'completion',
        method: 'POST',
        priority: 'high',
        retryCount: 0,
        maxRetries: config.rateLimit.maxRetries,
        execute: async () => {
          // Make request to Anthropic API
          const response = await axios.post(
            'https://api.anthropic.com/v1/messages',
            {
              model: config.ai.anthropic.model,
              system: `
                You are a natural language processing system that extracts structured information from user instructions.
                Extract the following information from the user's instruction:
                1. Topic - What the post is about
                2. Tone (optional) - The tone of the post (e.g., professional, casual, humorous)
                3. Content Type (optional) - The type of content (announcement, news, promotion, engagement, educational, entertainment, thread)
                4. Platforms - Which platforms to post to (twitter, mastodon, or all)
                5. Media Requirements (optional) - Whether to include images or videos
                6. Research Requirements (optional) - What research to include (hashtags, facts, trends, news)
                7. Scheduling Requirements (optional) - When to post
                
                Respond with a JSON object containing these fields.
              `,
              messages: [
                {
                  role: 'user',
                  content: instruction,
                },
              ],
              temperature: 0.1,
              max_tokens: 1000,
            },
            {
              headers: {
                'Content-Type': 'application/json',
                'x-api-key': config.ai.anthropic.apiKey,
                'anthropic-version': '2023-06-01',
              },
            }
          );
          
          return response.data;
        }
      });
      
      // Extract content from response
      const jsonString = result.content[0].text.trim();
      
      // Parse JSON
      const parsedIntent = JSON.parse(jsonString);
      
      // Convert to UserIntent
      const userIntent: UserIntent = {
        rawInput: instruction,
        topic: parsedIntent.topic || instruction,
        tone: parsedIntent.tone,
        contentType: this.parseContentType(parsedIntent.contentType),
        platforms: this.parsePlatforms(parsedIntent.platforms),
        mediaRequirements: parsedIntent.mediaRequirements,
        researchRequirements: parsedIntent.researchRequirements,
        schedulingRequirements: parsedIntent.schedulingRequirements,
      };
      
      logger.info('Intent parsed successfully with Anthropic', { 
        topic: userIntent.topic,
        platforms: userIntent.platforms,
      });
      
      return userIntent;
    } catch (error) {
      logger.error('Error parsing intent with Anthropic', { 
        instruction,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      // Fallback to rule-based parsing
      return this.parseIntentWithRules(instruction);
    }
  }
  
  /**
   * Parse intent with rule-based approach
   */
  private parseIntentWithRules(instruction: string): UserIntent {
    logger.info('Parsing intent with rules', { instruction });
    
    // Default intent
    const intent: UserIntent = {
      rawInput: instruction,
      topic: instruction,
      platforms: [SocialPlatform.TWITTER, SocialPlatform.MASTODON],
    };
    
    // Extract platforms
    if (instruction.toLowerCase().includes('twitter')) {
      intent.platforms = [SocialPlatform.TWITTER];
    } else if (instruction.toLowerCase().includes('mastodon')) {
      intent.platforms = [SocialPlatform.MASTODON];
    }
    
    // Extract content type
    if (instruction.toLowerCase().includes('announce')) {
      intent.contentType = ContentType.ANNOUNCEMENT;
    } else if (instruction.toLowerCase().includes('news')) {
      intent.contentType = ContentType.NEWS;
    } else if (instruction.toLowerCase().includes('promot')) {
      intent.contentType = ContentType.PROMOTION;
    } else if (instruction.toLowerCase().includes('engage')) {
      intent.contentType = ContentType.ENGAGEMENT;
    } else if (instruction.toLowerCase().includes('educat')) {
      intent.contentType = ContentType.EDUCATIONAL;
    } else if (instruction.toLowerCase().includes('entertain')) {
      intent.contentType = ContentType.ENTERTAINMENT;
    } else if (instruction.toLowerCase().includes('thread')) {
      intent.contentType = ContentType.THREAD;
    }
    
    // Extract tone
    if (instruction.toLowerCase().includes('professional')) {
      intent.tone = 'professional';
    } else if (instruction.toLowerCase().includes('casual')) {
      intent.tone = 'casual';
    } else if (instruction.toLowerCase().includes('humor')) {
      intent.tone = 'humorous';
    } else if (instruction.toLowerCase().includes('formal')) {
      intent.tone = 'formal';
    } else if (instruction.toLowerCase().includes('friendly')) {
      intent.tone = 'friendly';
    }
    
    // Extract research requirements
    intent.researchRequirements = {
      includeHashtags: instruction.toLowerCase().includes('hashtag'),
      includeFacts: instruction.toLowerCase().includes('fact'),
      includeTrends: instruction.toLowerCase().includes('trend'),
      includeNews: instruction.toLowerCase().includes('news'),
    };
    
    // Extract media requirements
    intent.mediaRequirements = {
      includeImage: instruction.toLowerCase().includes('image') || instruction.toLowerCase().includes('picture'),
      includeVideo: instruction.toLowerCase().includes('video'),
    };
    
    // Extract scheduling requirements
    intent.schedulingRequirements = {
      postImmediately: !instruction.toLowerCase().includes('schedule'),
      useOptimalTime: instruction.toLowerCase().includes('optimal'),
    };
    
    logger.info('Intent parsed successfully with rules', { 
      topic: intent.topic,
      platforms: intent.platforms,
    });
    
    return intent;
  }
  
  /**
   * Parse content type
   */
  private parseContentType(contentType?: string): ContentType | undefined {
    if (!contentType) return undefined;
    
    const contentTypeLower = contentType.toLowerCase();
    
    if (contentTypeLower.includes('announce')) {
      return ContentType.ANNOUNCEMENT;
    } else if (contentTypeLower.includes('news')) {
      return ContentType.NEWS;
    } else if (contentTypeLower.includes('promot')) {
      return ContentType.PROMOTION;
    } else if (contentTypeLower.includes('engage')) {
      return ContentType.ENGAGEMENT;
    } else if (contentTypeLower.includes('educat')) {
      return ContentType.EDUCATIONAL;
    } else if (contentTypeLower.includes('entertain')) {
      return ContentType.ENTERTAINMENT;
    } else if (contentTypeLower.includes('thread')) {
      return ContentType.THREAD;
    }
    
    return undefined;
  }
  
  /**
   * Parse platforms
   */
  private parsePlatforms(platforms?: string | string[]): SocialPlatform[] {
    if (!platforms) {
      return [SocialPlatform.TWITTER, SocialPlatform.MASTODON];
    }
    
    if (typeof platforms === 'string') {
      const platformsLower = platforms.toLowerCase();
      
      if (platformsLower === 'all') {
        return [SocialPlatform.TWITTER, SocialPlatform.MASTODON];
      } else if (platformsLower.includes('twitter')) {
        return [SocialPlatform.TWITTER];
      } else if (platformsLower.includes('mastodon')) {
        return [SocialPlatform.MASTODON];
      }
      
      return [SocialPlatform.TWITTER, SocialPlatform.MASTODON];
    }
    
    const result: SocialPlatform[] = [];
    
    for (const platform of platforms) {
      const platformLower = platform.toLowerCase();
      
      if (platformLower === 'all') {
        return [SocialPlatform.TWITTER, SocialPlatform.MASTODON];
      } else if (platformLower.includes('twitter')) {
        result.push(SocialPlatform.TWITTER);
      } else if (platformLower.includes('mastodon')) {
        result.push(SocialPlatform.MASTODON);
      }
    }
    
    return result.length > 0 ? result : [SocialPlatform.TWITTER, SocialPlatform.MASTODON];
  }
}

// Export singleton instance
export default new NLPProcessor();
