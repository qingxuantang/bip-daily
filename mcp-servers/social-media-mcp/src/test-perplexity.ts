import { createComponentLogger } from './utils/logger.js';
import perplexityClient from './research/perplexity/mcp-client.js';

const logger = createComponentLogger('PerplexityTest');

/**
 * Mock the use_mcp_tool function for testing
 */
// @ts-ignore
global.use_mcp_tool = async ({ server_name, tool_name, arguments: args }: any) => {
  logger.info('Mock MCP tool call', { server_name, tool_name, args });
  
  if (server_name === 'github.com/pashpashpash/perplexity-mcp' && tool_name === 'search') {
    // Return a mock response for the search tool
    return {
      text: `Artificial Intelligence (AI) is a branch of computer science focused on creating systems capable of performing tasks that typically require human intelligence.

AI encompasses various subfields including machine learning, natural language processing, computer vision, and robotics. Machine learning, particularly deep learning, has driven recent advances in AI by enabling systems to learn from data.

The field has seen significant growth and adoption across industries, from healthcare and finance to transportation and entertainment. AI technologies are being used to diagnose diseases, detect fraud, power autonomous vehicles, and create personalized recommendations.

Despite its benefits, AI raises important ethical considerations including privacy concerns, potential bias in algorithms, job displacement, and questions about accountability and transparency in AI decision-making.

Researchers continue to work on advancing AI capabilities while addressing these challenges, with a focus on developing responsible and beneficial AI systems.`,
      sources: [
        {
          title: 'Introduction to Artificial Intelligence',
          url: 'https://example.com/ai-intro',
          description: 'A comprehensive overview of artificial intelligence and its applications.'
        },
        {
          title: 'Machine Learning: The Core of Modern AI',
          url: 'https://example.com/machine-learning',
          description: 'How machine learning algorithms power today\'s AI systems.'
        },
        {
          title: 'Ethical Considerations in AI Development',
          url: 'https://example.com/ai-ethics',
          description: 'Exploring the ethical challenges and considerations in artificial intelligence.'
        }
      ]
    };
  }
  
  throw new Error(`Unsupported MCP tool: ${server_name}/${tool_name}`);
};

/**
 * Test the Perplexity MCP integration
 */
async function testPerplexityMcp() {
  logger.info('Testing Perplexity MCP integration');
  
  try {
    // Research a topic using the Perplexity client directly
    const topic = 'artificial intelligence';
    logger.info('Researching topic', { topic });
    
    const researchData = await perplexityClient.research(topic, {
      depth: 'detailed'
    });
    
    // Log the research data
    logger.info('Research data', {
      topic,
      factCount: researchData.facts?.length || 0,
      hashtagCount: researchData.hashtags?.length || 0,
      sourceCount: researchData.sources?.length || 0,
    });
    
    // Log the facts
    if (researchData.facts && researchData.facts.length > 0) {
      logger.info('Facts', { facts: researchData.facts });
    }
    
    // Log the hashtags
    if (researchData.hashtags && researchData.hashtags.length > 0) {
      logger.info('Hashtags', { hashtags: researchData.hashtags });
    }
    
    // Log the sources
    if (researchData.sources && researchData.sources.length > 0) {
      logger.info('Sources', { sources: researchData.sources });
    }
    
    logger.info('Perplexity MCP integration test completed successfully');
  } catch (error) {
    logger.error('Error testing Perplexity MCP integration', {
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

// Run the test
testPerplexityMcp().catch((error) => {
  logger.error('Unhandled error in test', {
    error: error instanceof Error ? error.message : String(error),
  });
});
