#!/usr/bin/env node
/**
 * Direct post to Twitter - bypasses MCP conversation flow
 * Supports thread posting for long content
 *
 * Usage: node direct-post.js "Your tweet content here" [image_path1] [image_path2] ...
 *
 * Examples:
 *   node direct-post.js "Hello world"
 *   node direct-post.js "Check out this image!" /path/to/image.png
 *   node direct-post.js "Multiple images!" /path/to/img1.png /path/to/img2.jpg
 *   node direct-post.js "Long content..." (automatically creates thread if > 280 chars)
 */

import twitterClient from './build/platforms/twitter/client.js';
import { existsSync } from 'fs';

// Twitter character limit (using 270 to leave room for thread numbering)
const TWEET_CHAR_LIMIT = 270;

/**
 * Split content into multiple tweets for a thread
 * @param {string} content - The full content to split
 * @returns {string[]} - Array of tweet parts
 */
function splitIntoThread(content) {
  // If content fits in one tweet, return as-is
  if (content.length <= TWEET_CHAR_LIMIT) {
    return [content];
  }

  const parts = [];

  // First, try to split by double newlines (paragraphs)
  const paragraphs = content.split(/\n\n+/);

  let currentPart = '';

  for (const paragraph of paragraphs) {
    const trimmedParagraph = paragraph.trim();
    if (!trimmedParagraph) continue;

    // If adding this paragraph exceeds limit
    if (currentPart.length + trimmedParagraph.length + 2 > TWEET_CHAR_LIMIT) {
      // Save current part if not empty
      if (currentPart.trim()) {
        parts.push(currentPart.trim());
      }

      // If the paragraph itself is too long, split it by sentences
      if (trimmedParagraph.length > TWEET_CHAR_LIMIT) {
        const sentenceParts = splitLongParagraph(trimmedParagraph);
        parts.push(...sentenceParts.slice(0, -1));
        currentPart = sentenceParts[sentenceParts.length - 1] || '';
      } else {
        currentPart = trimmedParagraph;
      }
    } else {
      // Add paragraph to current part
      currentPart = currentPart ? `${currentPart}\n\n${trimmedParagraph}` : trimmedParagraph;
    }
  }

  // Don't forget the last part
  if (currentPart.trim()) {
    parts.push(currentPart.trim());
  }

  return parts;
}

/**
 * Split a long paragraph by sentences
 * @param {string} paragraph - The paragraph to split
 * @returns {string[]} - Array of parts
 */
function splitLongParagraph(paragraph) {
  const parts = [];

  // Split by sentence endings (., !, ?, or Chinese punctuation)
  const sentences = paragraph.split(/(?<=[.!?。！？])\s*/);

  let currentPart = '';

  for (const sentence of sentences) {
    const trimmedSentence = sentence.trim();
    if (!trimmedSentence) continue;

    if (currentPart.length + trimmedSentence.length + 1 > TWEET_CHAR_LIMIT) {
      if (currentPart.trim()) {
        parts.push(currentPart.trim());
      }

      // If single sentence is too long, force split by character
      if (trimmedSentence.length > TWEET_CHAR_LIMIT) {
        const forceParts = forceSplit(trimmedSentence);
        parts.push(...forceParts.slice(0, -1));
        currentPart = forceParts[forceParts.length - 1] || '';
      } else {
        currentPart = trimmedSentence;
      }
    } else {
      currentPart = currentPart ? `${currentPart} ${trimmedSentence}` : trimmedSentence;
    }
  }

  if (currentPart.trim()) {
    parts.push(currentPart.trim());
  }

  return parts;
}

/**
 * Force split by character limit (last resort)
 * @param {string} text - Text to split
 * @returns {string[]} - Array of parts
 */
function forceSplit(text) {
  const parts = [];
  let remaining = text;

  while (remaining.length > TWEET_CHAR_LIMIT) {
    // Find a good break point (space, comma, etc.)
    let breakPoint = TWEET_CHAR_LIMIT;
    const searchStart = Math.max(0, TWEET_CHAR_LIMIT - 50);

    for (let i = TWEET_CHAR_LIMIT - 1; i >= searchStart; i--) {
      if (' ,，、'.includes(remaining[i])) {
        breakPoint = i + 1;
        break;
      }
    }

    parts.push(remaining.slice(0, breakPoint).trim() + '...');
    remaining = '...' + remaining.slice(breakPoint).trim();
  }

  if (remaining.trim()) {
    parts.push(remaining.trim());
  }

  return parts;
}

/**
 * Post a thread to Twitter
 * @param {string[]} parts - Array of tweet parts
 * @param {string[]} mediaPaths - Media paths (attached to first tweet only)
 * @returns {Promise<object>} - Result object
 */
async function postThread(parts, mediaPaths = []) {
  const results = [];
  let previousTweetId = null;

  console.log(`📎 Creating thread with ${parts.length} tweet(s)...`);

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    const isFirst = i === 0;

    console.log(`\n📝 Tweet ${i + 1}/${parts.length} (${part.length} chars):`);
    console.log(part.substring(0, 100) + (part.length > 100 ? '...' : ''));

    // Only attach media to the first tweet
    const mediaContent = isFirst && mediaPaths.length > 0
      ? mediaPaths.map(path => ({ type: 'image', url: path }))
      : [];

    // Create tweet options
    const tweetOptions = {
      text: part,
      platform: 'twitter',
      media: mediaContent.length > 0 ? mediaContent : undefined
    };

    // If not the first tweet, set as reply to previous
    if (previousTweetId) {
      tweetOptions.replyToTweetId = previousTweetId;
    }

    const result = await twitterClient.postTweet(tweetOptions);

    if (!result.success) {
      console.error(`❌ Failed to post tweet ${i + 1}:`, result.error);
      return {
        success: false,
        error: `Failed at tweet ${i + 1}: ${result.error}`,
        partialResults: results
      };
    }

    console.log(`✅ Tweet ${i + 1} posted: ${result.postId}`);
    results.push({
      part: i + 1,
      postId: result.postId,
      url: result.url
    });

    previousTweetId = result.postId;

    // Small delay between tweets to avoid rate limiting
    if (i < parts.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  return {
    success: true,
    isThread: parts.length > 1,
    tweetCount: parts.length,
    postId: results[0].postId,
    url: results[0].url,
    threadPosts: results
  };
}

async function directPost(content, mediaPaths = []) {
  try {
    console.log('Initializing Twitter client...');

    // Wait for client to be ready
    await new Promise(resolve => setTimeout(resolve, 3000));

    console.log('Posting to Twitter...');
    console.log('Content length:', content.length, 'chars');
    if (mediaPaths.length > 0) {
      console.log('Media:', mediaPaths);
    }

    // Split content into thread if necessary
    const parts = splitIntoThread(content);

    if (parts.length > 1) {
      console.log(`\n📎 Content exceeds ${TWEET_CHAR_LIMIT} chars, creating thread with ${parts.length} parts...`);
    }

    // Post as thread (works for single tweets too)
    const result = await postThread(parts, mediaPaths);

    if (result.success) {
      console.log('\n🎉 SUCCESS!');
      console.log('Tweet ID:', result.postId);
      console.log('URL:', result.url);
      if (result.isThread) {
        console.log(`Thread: ${result.tweetCount} tweets posted`);
      }

      // Output JSON for parsing
      console.log('---JSON---');
      console.log(JSON.stringify({
        success: true,
        postId: result.postId,
        url: result.url,
        mediaCount: mediaPaths.length,
        isThread: result.isThread || false,
        tweetCount: result.tweetCount || 1,
        threadPosts: result.threadPosts
      }));
    } else {
      console.error('FAILED:', result.error);
      console.log('---JSON---');
      console.log(JSON.stringify({
        success: false,
        error: result.error,
        partialResults: result.partialResults
      }));
    }

    return result;
  } catch (error) {
    console.error('Error:', error.message);
    console.log('---JSON---');
    console.log(JSON.stringify({
      success: false,
      error: error.message
    }));
    process.exit(1);
  }
}

// Get content and optional media paths from command line
const content = process.argv[2];
const mediaPaths = process.argv.slice(3).filter(path => {
  if (!existsSync(path)) {
    console.warn(`Warning: Media file not found: ${path}`);
    return false;
  }
  return true;
});

if (!content) {
  console.error('Usage: node direct-post.js "Your tweet content" [image_path1] [image_path2] ...');
  console.error('');
  console.error('Examples:');
  console.error('  node direct-post.js "Hello world"');
  console.error('  node direct-post.js "Check out this image!" /path/to/image.png');
  console.error('');
  console.error('Long content (>280 chars) is automatically split into a thread.');
  process.exit(1);
}

directPost(content, mediaPaths).then(() => {
  process.exit(0);
}).catch(() => {
  process.exit(1);
});
