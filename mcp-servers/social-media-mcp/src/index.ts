#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';

import config, { validateConfig } from './config/index.js';
import { createComponentLogger } from './utils/logger.js';
import { UserIntent, Content, SocialPlatform } from './types/index.js';

// Import components
import nlpProcessor from './nlp/index.js';
import researchAggregator from './research/aggregator/index.js';
import contentGenerator from './content/index.js';
import twitterClient from './platforms/twitter/client.js';
import mastodonClient from './platforms/mastodon/client.js';
import linkedinClient from './platforms/linkedin/client.js';
import historyManager from './history/manager.js';
import conversationManager, { ConversationState } from './conversation/manager.js';

const logger = createComponentLogger('Server');

/**
 * Social Media MCP Server
 * 
 * This server provides tools for creating and posting content to social media platforms
 * based on natural language instructions.
 */
class SocialMediaServer {
  private server: Server;

  constructor() {
    // Validate configuration
    validateConfig();

    // Initialize MCP server
    this.server = new Server(
      {
        name: config.server.name,
        version: config.server.version,
      },
      {
        capabilities: {
          resources: {},
          tools: {},
        },
      }
    );

    // Set up request handlers
    this.setupToolHandlers();
    
    // Error handling
    this.server.onerror = (error) => logger.error('MCP Error', { error });
    
    // Handle process signals
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });

    logger.info('Social Media MCP Server initialized');
  }

  /**
   * Set up tool handlers
   */
  private setupToolHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'create_post',
          description: 'Create and post content to social media platforms based on natural language instructions',
          inputSchema: {
            type: 'object',
            properties: {
              instruction: {
                type: 'string',
                description: 'Natural language instruction for the post (e.g., "Post about the latest AI developments")',
              },
              platforms: {
                type: 'array',
                items: {
                  type: 'string',
                  enum: ['twitter', 'mastodon', 'linkedin', 'all'],
                },
                description: 'Social media platforms to post to',
              },
              postImmediately: {
                type: 'boolean',
                description: 'Whether to post immediately or return a preview',
              },
              conversationId: {
                type: 'string',
                description: 'ID of an existing conversation to continue',
              },
              questionId: {
                type: 'string',
                description: 'ID of the question being answered',
              },
              answer: {
                type: 'string',
                description: 'Answer to the question',
              },
              ignoreHistory: {
                type: 'boolean',
                description: 'Whether to ignore similar posts in history',
              },
              actionableInsights: {
                type: 'boolean',
                description: 'Whether to include actionable insights in the post',
              },
            },
            required: ['instruction'],
          },
        },
        {
          name: 'get_trending_topics',
          description: 'Get trending topics from social media platforms',
          inputSchema: {
            type: 'object',
            properties: {
              platform: {
                type: 'string',
                enum: ['twitter', 'mastodon', 'linkedin', 'all'],
                description: 'Social media platform to get trending topics from',
              },
              category: {
                type: 'string',
                description: 'Category of trending topics (e.g., "technology", "entertainment")',
              },
              count: {
                type: 'number',
                description: 'Number of trending topics to return',
              },
            },
            required: ['platform'],
          },
        },
        {
          name: 'research_topic',
          description: 'Research a topic using Brave Search and Perplexity',
          inputSchema: {
            type: 'object',
            properties: {
              topic: {
                type: 'string',
                description: 'Topic to research',
              },
              includeHashtags: {
                type: 'boolean',
                description: 'Whether to include relevant hashtags',
              },
              includeFacts: {
                type: 'boolean',
                description: 'Whether to include facts about the topic',
              },
              includeTrends: {
                type: 'boolean',
                description: 'Whether to include trending information',
              },
              includeNews: {
                type: 'boolean',
                description: 'Whether to include news articles',
              },
            },
            required: ['topic'],
          },
        },
      ],
    }));

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        switch (request.params.name) {
          case 'create_post':
            return await this.handleCreatePost(request.params.arguments);
          case 'get_trending_topics':
            return await this.handleGetTrendingTopics(request.params.arguments);
          case 'research_topic':
            return await this.handleResearchTopic(request.params.arguments);
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${request.params.name}`
            );
        }
      } catch (error) {
        logger.error('Error handling tool call', { 
          tool: request.params.name, 
          error: error instanceof Error ? error.message : String(error) 
        });
        
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  /**
   * Handle create_post tool
   */
  private async handleCreatePost(args: any) {
    logger.info('Creating post', { instruction: args.instruction });
    
    try {
      // Get conversation ID if provided
      const conversationId = args.conversationId;
      
      // Parse the instruction to extract intent
      const intent = await nlpProcessor.parseIntent(args.instruction, conversationId);
      
      // Override platforms if specified in args
      if (args.platforms) {
        if (args.platforms === 'all') {
          intent.platforms = [SocialPlatform.TWITTER, SocialPlatform.MASTODON, SocialPlatform.LINKEDIN];
        } else if (Array.isArray(args.platforms)) {
          intent.platforms = [];
          if (args.platforms.includes('twitter')) {
            intent.platforms.push(SocialPlatform.TWITTER);
          }
          if (args.platforms.includes('mastodon')) {
            intent.platforms.push(SocialPlatform.MASTODON);
          }
          if (args.platforms.includes('linkedin')) {
            intent.platforms.push(SocialPlatform.LINKEDIN);
          }
        }
      }
      
      // Override scheduling requirements if postImmediately is specified
      if (args.postImmediately !== undefined) {
        if (!intent.schedulingRequirements) {
          intent.schedulingRequirements = {};
        }
        intent.schedulingRequirements.postImmediately = args.postImmediately;
      }
      
      // Set actionable insights if specified
      if (args.actionableInsights !== undefined) {
        intent.actionableInsights = args.actionableInsights ? 
          'Include practical steps that readers can take immediately.' : undefined;
      }
      
      // Check if there are similar posts in history (unless ignoreHistory is true)
      if (!args.ignoreHistory) {
        const similarPosts = historyManager.getSimilarPosts(intent.topic, 0.7);
        
        if (similarPosts.length > 0) {
          logger.info('Found similar posts in history', { 
            count: similarPosts.length,
            topic: intent.topic,
          });
          
          // Return similar posts
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  instruction: args.instruction,
                  intent,
                  similarPosts,
                  status: 'similar_posts_found',
                  message: 'Similar posts were found in history. Consider modifying your topic or focusing on a different aspect.',
                }, null, 2),
              },
            ],
          };
        }
      } else {
        logger.info('Ignoring history check', { topic: intent.topic });
      }
      
      // Create or get conversation
      let conversation;
      if (conversationId) {
        conversation = conversationManager.getConversation(conversationId);
        if (!conversation) {
          logger.warn('Conversation not found, creating new conversation', { conversationId });
          conversation = conversationManager.createConversation(intent);
        }
      } else {
        conversation = conversationManager.createConversation(intent);
      }
      
      // Store conversation ID in intent
      intent.conversationId = conversation.id;
      
      // Check if we need to ask questions
      if (conversation.state === ConversationState.INITIAL_REQUEST) {
        // Generate questions
        const questionIds = conversationManager.generateQuestions(conversation.id);
        
        if (questionIds.length > 0) {
          // Get the first question
          const question = conversationManager.getCurrentQuestion(conversation.id);
          
          if (question) {
            logger.info('Asking question', { 
              conversationId: conversation.id,
              questionId: question.id,
              questionType: question.type,
            });
            
            // Return question
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify({
                    instruction: args.instruction,
                    intent,
                    conversationId: conversation.id,
                    question: question.text,
                    questionId: question.id,
                    status: 'question',
                  }, null, 2),
                },
              ],
            };
          }
        }
      } else if (conversation.state === ConversationState.ASKING_QUESTIONS) {
        // Check if we have a question to answer
        if (args.questionId && args.answer) {
          // Answer the question
          conversationManager.answerQuestion(conversation.id, args.questionId, args.answer);
          
          // Get the next question
          const nextQuestion = conversationManager.getCurrentQuestion(conversation.id);
          
          if (nextQuestion) {
            logger.info('Asking next question', { 
              conversationId: conversation.id,
              questionId: nextQuestion.id,
              questionType: nextQuestion.type,
            });
            
            // Return next question
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify({
                    instruction: args.instruction,
                    intent,
                    conversationId: conversation.id,
                    question: nextQuestion.text,
                    questionId: nextQuestion.id,
                    status: 'question',
                  }, null, 2),
                },
              ],
            };
          }
        } else {
          // Get the current question
          const currentQuestion = conversationManager.getCurrentQuestion(conversation.id);
          
          if (currentQuestion) {
            logger.info('Asking current question', { 
              conversationId: conversation.id,
              questionId: currentQuestion.id,
              questionType: currentQuestion.type,
            });
            
            // Return current question
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify({
                    instruction: args.instruction,
                    intent,
                    conversationId: conversation.id,
                    question: currentQuestion.text,
                    questionId: currentQuestion.id,
                    status: 'question',
                  }, null, 2),
                },
              ],
            };
          }
        }
      }
      
      // Update conversation state to generating content
      conversationManager.updateState(conversation.id, ConversationState.GENERATING_CONTENT);
      
      // Research the topic
      const researchOptions = {
        includeHashtags: intent.researchRequirements?.includeHashtags || true,
        includeFacts: intent.researchRequirements?.includeFacts || true,
        includeTrends: intent.researchRequirements?.includeTrends || true,
        includeNews: intent.researchRequirements?.includeNews || true,
      };
      
      const research = await researchAggregator.researchTopic(intent.topic, researchOptions);
      
      // Generate content for each platform
      const content = await contentGenerator.generateContentForPlatforms(
        intent,
        research,
        intent.platforms
      );
      
      // Update conversation state to preview
      conversationManager.updateState(conversation.id, ConversationState.PREVIEW);
      
      // Post content if postImmediately is true
      if (intent.schedulingRequirements?.postImmediately) {
        const postResults = await this.postContent(content);
        
        // Update conversation state to completed
        conversationManager.updateState(conversation.id, ConversationState.COMPLETED);
        
        // Add to history
        const keywords = research.hashtags || [];
        historyManager.addToHistory(
          intent.topic,
          args.instruction,
          intent.platforms,
          content,
          keywords
        );
        
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                instruction: args.instruction,
                intent,
                research,
                content,
                postResults,
                conversationId: conversation.id,
                status: 'posted',
              }, null, 2),
            },
          ],
        };
      }
      
      // Return preview if postImmediately is false
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              instruction: args.instruction,
              intent,
              research,
              content,
              conversationId: conversation.id,
              status: 'preview',
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Error creating post', { 
        instruction: args.instruction,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Post content to platforms
   */
  private async postContent(content: Record<SocialPlatform, Content>): Promise<any> {
    const results: Record<string, any> = {};
    
    // Post to Twitter
    if (content[SocialPlatform.TWITTER]) {
      try {
        results.twitter = await twitterClient.postTweet(content[SocialPlatform.TWITTER]);
      } catch (error) {
        logger.error('Error posting to Twitter', { 
          error: error instanceof Error ? error.message : String(error) 
        });
        
        results.twitter = {
          success: false,
          error: error instanceof Error ? error.message : String(error),
        };
      }
    }
    
    // Post to Mastodon
    if (content[SocialPlatform.MASTODON]) {
      try {
        results.mastodon = await mastodonClient.postStatus(content[SocialPlatform.MASTODON]);
      } catch (error) {
        logger.error('Error posting to Mastodon', { 
          error: error instanceof Error ? error.message : String(error) 
        });
        
        results.mastodon = {
          success: false,
          error: error instanceof Error ? error.message : String(error),
        };
      }
    }
    
    // Post to LinkedIn
    if (content[SocialPlatform.LINKEDIN]) {
      try {
        results.linkedin = await linkedinClient.postShare(content[SocialPlatform.LINKEDIN]);
      } catch (error) {
        logger.error('Error posting to LinkedIn', { 
          error: error instanceof Error ? error.message : String(error) 
        });
        
        results.linkedin = {
          success: false,
          error: error instanceof Error ? error.message : String(error),
        };
      }
    }
    
    return results;
  }

  /**
   * Handle get_trending_topics tool
   */
  private async handleGetTrendingTopics(args: any) {
    logger.info('Getting trending topics', { platform: args.platform });
    
    try {
      const platform = args.platform || 'all';
      const category = args.category || 'all';
      const count = args.count || 10;
      
      const results: Record<string, any> = {};
      
      // Get Twitter trending topics
      if (platform === 'all' || platform === 'twitter') {
        try {
          results.twitter = await twitterClient.getTrendingTopics(category, count);
        } catch (error) {
          logger.error('Error getting Twitter trending topics', { 
            error: error instanceof Error ? error.message : String(error) 
          });
          
          results.twitter = [];
        }
      }
      
      // Get Mastodon trending tags
      if (platform === 'all' || platform === 'mastodon') {
        try {
          results.mastodon = await mastodonClient.getTrendingTags(count);
        } catch (error) {
          logger.error('Error getting Mastodon trending tags', { 
            error: error instanceof Error ? error.message : String(error) 
          });
          
          results.mastodon = [];
        }
      }
      
      // Get LinkedIn trending topics
      if (platform === 'all' || platform === 'linkedin') {
        try {
          results.linkedin = await linkedinClient.getTrendingTopics(count);
        } catch (error) {
          logger.error('Error getting LinkedIn trending topics', { 
            error: error instanceof Error ? error.message : String(error) 
          });
          
          results.linkedin = [];
        }
      }
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              platform,
              category,
              count,
              trendingTopics: platform === 'all' ? results : results[platform],
              status: 'success',
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Error getting trending topics', { 
        platform: args.platform,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Handle research_topic tool
   */
  private async handleResearchTopic(args: any) {
    logger.info('Researching topic', { topic: args.topic });
    
    try {
      const topic = args.topic;
      const options = {
        includeHashtags: args.includeHashtags || false,
        includeFacts: args.includeFacts || false,
        includeTrends: args.includeTrends || false,
        includeNews: args.includeNews || false,
      };
      
      const researchData = await researchAggregator.researchTopic(topic, options);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              topic,
              options,
              researchData,
              status: 'success',
            }, null, 2),
          },
        ],
      };
    } catch (error) {
      logger.error('Error researching topic', { 
        topic: args.topic,
        error: error instanceof Error ? error.message : String(error) 
      });
      
      throw error;
    }
  }

  /**
   * Run the server
   */
  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    logger.info('Social Media MCP Server running on stdio');
  }
}

// Create and run the server
const server = new SocialMediaServer();
server.run().catch((error) => {
  logger.error('Error running server', { error });
  process.exit(1);
});
