import { createComponentLogger } from './utils/logger.js';
import twitterClient from './platforms/twitter/client.js';
import linkedinClient from './platforms/linkedin/client.js';
import { Content, SocialPlatform } from './types/index.js';

const logger = createComponentLogger('PlatformTest');

/**
 * Test function for Twitter client
 */
async function testTwitter() {
  logger.info('Testing Twitter client...');
  
  try {
    // Test getting trending topics
    logger.info('Testing Twitter trending topics...');
    const trendingTopics = await twitterClient.getTrendingTopics();
    logger.info('Twitter trending topics retrieved successfully', { 
      count: trendingTopics.length,
      topics: trendingTopics.slice(0, 3) // Log first 3 topics
    });
    
    // Test posting a tweet (commented out to avoid actual posting during testing)
    /*
    logger.info('Testing Twitter posting...');
    const content: Content = {
      text: `Test tweet from Social Media MCP Server - ${new Date().toISOString()}`,
      platform: SocialPlatform.TWITTER
    };
    const postResult = await twitterClient.postTweet(content);
    logger.info('Twitter post result', { result: postResult });
    
    // Test getting engagement metrics
    if (postResult.success) {
      logger.info('Testing Twitter engagement metrics...');
      const metrics = await twitterClient.getEngagementMetrics(postResult.postId);
      logger.info('Twitter engagement metrics retrieved successfully', { metrics });
    }
    */
    
    logger.info('Twitter client tests completed successfully');
    return true;
  } catch (error) {
    logger.error('Error testing Twitter client', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    return false;
  }
}

/**
 * Test function for LinkedIn client
 */
async function testLinkedIn() {
  logger.info('Testing LinkedIn client...');
  
  try {
    // Test getting trending topics
    logger.info('Testing LinkedIn trending topics...');
    const trendingTopics = await linkedinClient.getTrendingTopics();
    logger.info('LinkedIn trending topics retrieved successfully', { 
      count: trendingTopics.length,
      topics: trendingTopics.slice(0, 3) // Log first 3 topics
    });
    
    // Test posting a share (commented out to avoid actual posting during testing)
    /*
    logger.info('Testing LinkedIn posting...');
    const content: Content = {
      text: `Test share from Social Media MCP Server - ${new Date().toISOString()}`,
      platform: SocialPlatform.LINKEDIN
    };
    const postResult = await linkedinClient.postShare(content);
    logger.info('LinkedIn post result', { result: postResult });
    
    // Test getting engagement metrics
    if (postResult.success) {
      logger.info('Testing LinkedIn engagement metrics...');
      const metrics = await linkedinClient.getEngagementMetrics(postResult.postId);
      logger.info('LinkedIn engagement metrics retrieved successfully', { metrics });
    }
    */
    
    logger.info('LinkedIn client tests completed successfully');
    return true;
  } catch (error) {
    logger.error('Error testing LinkedIn client', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    return false;
  }
}

/**
 * Main test function
 */
async function runTests() {
  logger.info('Starting platform tests...');
  
  const twitterResult = await testTwitter();
  const linkedinResult = await testLinkedIn();
  
  logger.info('Platform tests completed', { 
    twitter: twitterResult ? 'Success' : 'Failed',
    linkedin: linkedinResult ? 'Success' : 'Failed'
  });
}

// Run tests
runTests().catch(error => {
  logger.error('Unhandled error in tests', { 
    error: error instanceof Error ? error.message : String(error) 
  });
});
