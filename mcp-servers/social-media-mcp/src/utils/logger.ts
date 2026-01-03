import winston from 'winston';
import config from '../config/index.js';

// Define log format
const logFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.printf(({ level, message, timestamp, stack, ...meta }) => {
    const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
    const stackStr = stack ? `\n${stack}` : '';
    return `${timestamp} [${level.toUpperCase()}] ${message}${metaStr}${stackStr}`;
  })
);

// Create logger instance
const logger = winston.createLogger({
  level: config.server.logLevel,
  format: logFormat,
  transports: [
    // Console transport
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        logFormat
      ),
    }),
    // File transport for errors
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error',
    }),
    // File transport for all logs
    new winston.transports.File({
      filename: 'logs/combined.log',
    }),
  ],
});

// Create component-specific loggers
const createComponentLogger = (component: string) => {
  return {
    debug: (message: string, meta: object = {}) => logger.debug(`[${component}] ${message}`, meta),
    info: (message: string, meta: object = {}) => logger.info(`[${component}] ${message}`, meta),
    warn: (message: string, meta: object = {}) => logger.warn(`[${component}] ${message}`, meta),
    error: (message: string, meta: object = {}) => logger.error(`[${component}] ${message}`, meta),
  };
};

export default logger;
export { createComponentLogger };
