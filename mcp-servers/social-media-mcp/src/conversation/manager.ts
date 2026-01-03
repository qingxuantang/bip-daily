import { createComponentLogger } from '../utils/logger.js';
import { UserIntent, SocialPlatform } from '../types/index.js';
import crypto from 'crypto';

const logger = createComponentLogger('ConversationManager');

/**
 * Conversation state
 */
export enum ConversationState {
  INITIAL_REQUEST = 'initial_request',
  ASKING_QUESTIONS = 'asking_questions',
  GENERATING_CONTENT = 'generating_content',
  PREVIEW = 'preview',
  POSTING = 'posting',
  COMPLETED = 'completed',
}

/**
 * Question type
 */
export enum QuestionType {
  AUDIENCE = 'audience',
  TOPIC_CLARIFICATION = 'topic_clarification',
  GOAL = 'goal',
  TONE = 'tone',
  ACTIONABLE_INSIGHTS = 'actionable_insights',
  TECHNICAL_LEVEL = 'technical_level',
  EXAMPLES = 'examples',
  FOCUS = 'focus',
}

/**
 * Question
 */
export interface Question {
  id: string;
  type: QuestionType;
  text: string;
  answered: boolean;
  answer?: string;
}

/**
 * Conversation
 */
export interface Conversation {
  id: string;
  state: ConversationState;
  intent: UserIntent;
  questions: Question[];
  currentQuestionIndex: number;
  timestamp: string;
  lastUpdated: string;
}

/**
 * Conversation manager for handling multi-turn conversations
 */
class ConversationManager {
  private conversations: Map<string, Conversation> = new Map();

  constructor() {
    logger.info('Conversation manager initialized');
  }

  /**
   * Create a new conversation
   */
  createConversation(intent: UserIntent): Conversation {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    
    const conversation: Conversation = {
      id,
      state: ConversationState.INITIAL_REQUEST,
      intent,
      questions: [],
      currentQuestionIndex: -1,
      timestamp: now,
      lastUpdated: now,
    };
    
    this.conversations.set(id, conversation);
    
    logger.info('Conversation created', { id });
    
    return conversation;
  }

  /**
   * Get a conversation by ID
   */
  getConversation(id: string): Conversation | undefined {
    return this.conversations.get(id);
  }

  /**
   * Update conversation state
   */
  updateState(id: string, state: ConversationState): boolean {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return false;
    }
    
    conversation.state = state;
    conversation.lastUpdated = new Date().toISOString();
    
    logger.info('Conversation state updated', { id, state });
    
    return true;
  }

  /**
   * Add a question to a conversation
   */
  addQuestion(id: string, type: QuestionType, text: string): string | null {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return null;
    }
    
    const questionId = crypto.randomUUID();
    
    const question: Question = {
      id: questionId,
      type,
      text,
      answered: false,
    };
    
    conversation.questions.push(question);
    
    // If this is the first question, set the current question index
    if (conversation.currentQuestionIndex === -1) {
      conversation.currentQuestionIndex = 0;
      conversation.state = ConversationState.ASKING_QUESTIONS;
    }
    
    conversation.lastUpdated = new Date().toISOString();
    
    logger.info('Question added to conversation', { 
      conversationId: id, 
      questionId,
      type,
    });
    
    return questionId;
  }

  /**
   * Get the current question for a conversation
   */
  getCurrentQuestion(id: string): Question | null {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return null;
    }
    
    if (conversation.currentQuestionIndex === -1 || 
        conversation.currentQuestionIndex >= conversation.questions.length) {
      return null;
    }
    
    return conversation.questions[conversation.currentQuestionIndex];
  }

  /**
   * Answer a question
   */
  answerQuestion(id: string, questionId: string, answer: string): boolean {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return false;
    }
    
    const questionIndex = conversation.questions.findIndex(q => q.id === questionId);
    
    if (questionIndex === -1) {
      logger.warn('Question not found', { conversationId: id, questionId });
      return false;
    }
    
    const question = conversation.questions[questionIndex];
    question.answered = true;
    question.answer = answer;
    
    // Update the intent based on the answer
    this.updateIntentWithAnswer(conversation, question);
    
    // Move to the next question
    conversation.currentQuestionIndex++;
    
    // If all questions are answered, move to generating content
    if (conversation.currentQuestionIndex >= conversation.questions.length) {
      conversation.state = ConversationState.GENERATING_CONTENT;
    }
    
    conversation.lastUpdated = new Date().toISOString();
    
    logger.info('Question answered', { 
      conversationId: id, 
      questionId,
      nextQuestionIndex: conversation.currentQuestionIndex,
    });
    
    return true;
  }

  /**
   * Update intent with answer
   */
  private updateIntentWithAnswer(conversation: Conversation, question: Question): void {
    const intent = conversation.intent;
    const answer = question.answer || '';
    
    switch (question.type) {
      case QuestionType.AUDIENCE:
        // Store audience information in the intent
        if (!intent.audience) {
          intent.audience = answer;
        }
        break;
        
      case QuestionType.TOPIC_CLARIFICATION:
        // Update the topic with clarification
        intent.topic = answer;
        break;
        
      case QuestionType.GOAL:
        // Store goal information in the intent
        if (!intent.goal) {
          intent.goal = answer;
        }
        break;
        
      case QuestionType.TONE:
        // Update the tone
        intent.tone = answer;
        break;
        
      case QuestionType.ACTIONABLE_INSIGHTS:
        // Store actionable insights requirement
        if (!intent.actionableInsights) {
          intent.actionableInsights = answer;
        }
        break;
        
      case QuestionType.TECHNICAL_LEVEL:
        // Store technical level information
        if (!intent.technicalLevel) {
          intent.technicalLevel = answer;
        }
        break;
        
      case QuestionType.EXAMPLES:
        // Store examples
        if (!intent.examples) {
          intent.examples = answer;
        }
        break;
        
      case QuestionType.FOCUS:
        // Store focus information
        if (!intent.focus) {
          intent.focus = answer;
        }
        break;
    }
  }

  /**
   * Generate questions for a conversation
   */
  generateQuestions(id: string): string[] {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return [];
    }
    
    const intent = conversation.intent;
    const questionIds: string[] = [];
    
    // Check if we need to ask about the audience
    if (!intent.audience) {
      const questionId = this.addQuestion(
        id,
        QuestionType.AUDIENCE,
        'Who is the target audience for this content?'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // Check if we need to clarify the topic
    if (intent.topic.length < 10 || intent.topic.split(' ').length < 3) {
      const questionId = this.addQuestion(
        id,
        QuestionType.TOPIC_CLARIFICATION,
        'Could you provide more details about the topic you want to cover?'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // Check if we need to ask about the goal
    if (!intent.goal) {
      const questionId = this.addQuestion(
        id,
        QuestionType.GOAL,
        'What is the main goal of this post? (e.g., educate, engage, promote)'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // Check if we need to ask about the tone
    if (!intent.tone) {
      const questionId = this.addQuestion(
        id,
        QuestionType.TONE,
        'What tone would you like for this post? (e.g., professional, casual, humorous)'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // Check if we need to ask about actionable insights
    if (intent.rawInput.toLowerCase().includes('action') && !intent.actionableInsights) {
      const questionId = this.addQuestion(
        id,
        QuestionType.ACTIONABLE_INSIGHTS,
        'What kind of actionable insights or steps would you like to include?'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // Check if we need to ask about technical level
    if (intent.rawInput.toLowerCase().includes('technical') && !intent.technicalLevel) {
      const questionId = this.addQuestion(
        id,
        QuestionType.TECHNICAL_LEVEL,
        'What technical level should the content be aimed at? (e.g., beginner, intermediate, advanced)'
      );
      if (questionId) questionIds.push(questionId);
    }
    
    // If no questions were added, move to generating content
    if (questionIds.length === 0) {
      conversation.state = ConversationState.GENERATING_CONTENT;
    }
    
    logger.info('Questions generated', { 
      conversationId: id, 
      questionCount: questionIds.length,
    });
    
    return questionIds;
  }

  /**
   * Check if all questions have been answered
   */
  areAllQuestionsAnswered(id: string): boolean {
    const conversation = this.conversations.get(id);
    
    if (!conversation) {
      logger.warn('Conversation not found', { id });
      return false;
    }
    
    return conversation.questions.every(q => q.answered);
  }

  /**
   * Delete a conversation
   */
  deleteConversation(id: string): boolean {
    const result = this.conversations.delete(id);
    
    if (result) {
      logger.info('Conversation deleted', { id });
    } else {
      logger.warn('Conversation not found', { id });
    }
    
    return result;
  }
}

// Export singleton instance
export default new ConversationManager();
