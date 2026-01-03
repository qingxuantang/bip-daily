import { createComponentLogger } from './utils/logger.js';
import linkedinClient from './platforms/linkedin/client.js';
import mastodonClient from './platforms/mastodon/client.js';
import { Content, SocialPlatform } from './types/index.js';
import historyManager from './history/manager.js';
import fs from 'fs';

const logger = createComponentLogger('ActionableMCPPost');

/**
 * Post actionable MCP content to Mastodon
 */
async function postToMastodon(content: Content): Promise<boolean> {
  logger.info('Posting to Mastodon...');
  
  try {
    // Post to Mastodon
    logger.info('Posting to Mastodon...', { content: content.text.substring(0, 30) + '...' });
    
    // Check if mastodonClient has a postStatus method
    if ('postStatus' in mastodonClient) {
      const postResult = await (mastodonClient as any).postStatus(content);
      
      // Log result
      if (postResult.success) {
        logger.info('Mastodon post successful', { 
          id: postResult.postId,
          url: postResult.url,
          isMock: postResult.isMock
        });
        
        // Print to console for user visibility
        console.log('\nMastodon post successful!');
        console.log(`URL: ${postResult.url}`);
        if (postResult.isMock) {
          console.log('Note: This was a mock post. To post for real, check Mastodon credentials.');
        }
        
        return true;
      } else {
        logger.error('Mastodon post failed', { error: postResult.error });
        console.log('\nMastodon post failed:', postResult.error);
        return false;
      }
    } else {
      logger.error('Mastodon client does not have a postStatus method');
      console.log('\nError: Mastodon client does not have a postStatus method');
      return false;
    }
  } catch (error) {
    logger.error('Error posting to Mastodon', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    console.log('\nError posting to Mastodon:', error instanceof Error ? error.message : String(error));
    return false;
  }
}

/**
 * Post actionable MCP content to LinkedIn
 */
async function postToLinkedIn(content: Content): Promise<boolean> {
  logger.info('Posting to LinkedIn...');
  
  try {
    // Post to LinkedIn
    logger.info('Posting to LinkedIn...', { content: content.text.substring(0, 30) + '...' });
    const postResult = await linkedinClient.postShare(content);
    
    // Log result
    if (postResult.success) {
      logger.info('LinkedIn post successful', { 
        id: postResult.postId,
        url: postResult.url,
        isMock: postResult.isMock
      });
      
      // Print to console for user visibility
      console.log('\nLinkedIn post successful!');
      console.log(`URL: ${postResult.url}`);
      if (postResult.isMock) {
        console.log('Note: This was a mock post. To post for real, check LinkedIn credentials.');
      }
      
      return true;
    } else {
      logger.error('LinkedIn post failed', { error: postResult.error });
      console.log('\nLinkedIn post failed:', postResult.error);
      return false;
    }
  } catch (error) {
    logger.error('Error posting to LinkedIn', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    console.log('\nError posting to LinkedIn:', error instanceof Error ? error.message : String(error));
    return false;
  }
}

/**
 * Add content to history
 */
async function addToHistory(mastodonContent: Content, linkedinContent: Content): Promise<string> {
  logger.info('Adding to history...');
  
  try {
    // Create history entry
    const topic = 'Actionable MCP Server Projects';
    const instruction = 'Create actionable content about practical MCP server projects';
    const platforms = [SocialPlatform.MASTODON, SocialPlatform.LINKEDIN];
    
    // Create a dummy Twitter content to satisfy the type requirements
    const twitterContent: Content = {
      text: "This content was not posted to Twitter",
      platform: SocialPlatform.TWITTER
    };
    
    const content = {
      [SocialPlatform.TWITTER]: twitterContent,
      [SocialPlatform.MASTODON]: mastodonContent,
      [SocialPlatform.LINKEDIN]: linkedinContent,
    };
    const keywords = ['MCP', 'AI', 'DevProjects', 'BusinessIntelligence', 'ROI'];
    
    // Add to history
    const id = historyManager.addToHistory(topic, instruction, platforms, content, keywords);
    logger.info('Added to history', { id });
    
    // Print to console for user visibility
    console.log('\nContent added to history with ID:', id);
    
    return id;
  } catch (error) {
    logger.error('Error adding to history', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    console.log('\nError adding to history:', error instanceof Error ? error.message : String(error));
    return '';
  }
}

/**
 * Main function to post actionable MCP content
 */
async function postActionableMCPContent() {
  console.log('Starting to post actionable MCP content...');
  logger.info('Starting actionable MCP content posting...');
  
  try {
    // Read the content file
    logger.info('Reading actionable MCP content...');
    const contentRaw = fs.readFileSync('./actionable-mcp-content.json', 'utf-8');
    const content = JSON.parse(contentRaw);
    
    // Create content objects
    const mastodonContent: Content = {
      text: content.mastodon.post,
      platform: SocialPlatform.MASTODON
    };
    
    const linkedinContent: Content = {
      text: content.linkedin.post,
      platform: SocialPlatform.LINKEDIN
    };
    
    // Post to platforms
    const mastodonResult = await postToMastodon(mastodonContent);
    const linkedinResult = await postToLinkedIn(linkedinContent);
    
    // Add to history
    let historyId = '';
    if (mastodonResult || linkedinResult) {
      historyId = await addToHistory(mastodonContent, linkedinContent);
    }
    
    // Log overall results
    logger.info('Actionable MCP content posting completed', { 
      mastodon: mastodonResult ? 'Success' : 'Failed',
      linkedin: linkedinResult ? 'Success' : 'Failed',
      historyId
    });
    
    console.log('\n===== POSTING SUMMARY =====');
    console.log(`Mastodon: ${mastodonResult ? 'SUCCESS' : 'FAILED'}`);
    console.log(`LinkedIn: ${linkedinResult ? 'SUCCESS' : 'FAILED'}`);
    console.log(`History ID: ${historyId || 'Not added'}`);
    
    return {
      mastodon: mastodonResult,
      linkedin: linkedinResult,
      historyId
    };
  } catch (error) {
    logger.error('Error posting actionable MCP content', { 
      error: error instanceof Error ? error.message : String(error) 
    });
    console.log('\nError posting actionable MCP content:', error instanceof Error ? error.message : String(error));
    return {
      mastodon: false,
      linkedin: false,
      historyId: ''
    };
  }
}

// Run the main function
postActionableMCPContent().catch(error => {
  logger.error('Unhandled error in actionable MCP content posting', { 
    error: error instanceof Error ? error.message : String(error) 
  });
  console.error('Unhandled error:', error);
});
