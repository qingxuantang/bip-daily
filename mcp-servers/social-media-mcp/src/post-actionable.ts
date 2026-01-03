// Script to post actionable MCP content to Mastodon and LinkedIn
import fs from 'fs';
import mastodonClient from './platforms/mastodon/client.js';
import linkedinClient from './platforms/linkedin/client.js';
import { SocialPlatform } from './types/index.js';
import { createComponentLogger } from './utils/logger.js';

const logger = createComponentLogger('ActionablePost');

/**
 * Post actionable MCP content to Mastodon and LinkedIn
 */
async function postActionableContent() {
  logger.info('Starting actionable MCP content posting...');
  
  try {
    // Read the content file
    logger.info('Reading actionable MCP content...');
    const contentRaw = fs.readFileSync('./actionable-mcp-content.json', 'utf-8');
    const content = JSON.parse(contentRaw);
    
    // Post to Mastodon
    logger.info('Posting to Mastodon...');
    const mastodonContent = {
      text: content.mastodon.post,
      platform: SocialPlatform.MASTODON
    };
    
    logger.info('Posting to Mastodon...', { content: mastodonContent.text.substring(0, 30) + '...' });
    const mastodonResult = await mastodonClient.postStatus(mastodonContent);
    
    logger.info('Mastodon post result', { 
      success: mastodonResult.success,
      id: mastodonResult.postId,
      url: mastodonResult.url,
      isMock: mastodonResult.isMock
    });
    
    // Post to LinkedIn
    logger.info('Posting to LinkedIn...');
    const linkedinContent = {
      text: content.linkedin.post,
      platform: SocialPlatform.LINKEDIN
    };
    
    logger.info('Posting to LinkedIn...', { content: linkedinContent.text.substring(0, 30) + '...' });
    const linkedinResult = await linkedinClient.postShare(linkedinContent);
    
    logger.info('LinkedIn post result', { 
      success: linkedinResult.success,
      id: linkedinResult.postId,
      url: linkedinResult.url,
      isMock: linkedinResult.isMock
    });
    
    // Log overall results
    logger.info('Actionable MCP content posting completed', { 
      mastodon: mastodonResult.success ? 'Success' : 'Failed',
      linkedin: linkedinResult.success ? 'Success' : 'Failed'
    });
    
    return {
      mastodon: { 
        success: mastodonResult.success, 
        id: mastodonResult.postId, 
        url: mastodonResult.url,
        isMock: mastodonResult.isMock
      },
      linkedin: { 
        success: linkedinResult.success, 
        id: linkedinResult.postId, 
        url: linkedinResult.url,
        isMock: linkedinResult.isMock
      }
    };
  } catch (error) {
    logger.error('Error posting actionable MCP content', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    throw error;
  }
}

// Run the function
postActionableContent().then(results => {
  console.log('\n===== POSTING SUMMARY =====');
  console.log(`Mastodon: ${results.mastodon.success ? 'SUCCESS' : 'FAILED'} ${results.mastodon.isMock ? '(MOCK)' : ''}`);
  if (results.mastodon.success) {
    console.log(`URL: ${results.mastodon.url}`);
  }
  
  console.log(`LinkedIn: ${results.linkedin.success ? 'SUCCESS' : 'FAILED'} ${results.linkedin.isMock ? '(MOCK)' : ''}`);
  if (results.linkedin.success) {
    console.log(`URL: ${results.linkedin.url}`);
  }
  
  // Check if any posts were mocks and provide guidance
  if (results.mastodon.isMock) {
    console.log('\nMastodon post used mock implementation. To fix:');
    console.log('1. Check Mastodon credentials in config/index.ts');
    console.log('2. Ensure you have a valid access token for your Mastodon instance');
    console.log('3. Rebuild and try again');
  }
  
  if (results.linkedin.isMock) {
    console.log('\nLinkedIn post used mock implementation. To fix:');
    console.log('1. Check LinkedIn credentials in config/index.ts');
    console.log('2. Ensure you have a valid access token for LinkedIn');
    console.log('3. Rebuild and try again');
  }
}).catch(error => {
  console.error('Unhandled error:', error);
});
