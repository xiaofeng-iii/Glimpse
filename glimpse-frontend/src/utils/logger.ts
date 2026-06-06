type LogLevel = 'debug' | 'info' | 'warn' | 'error'

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
}

const ENV_LOG_LEVEL = (import.meta.env.VITE_LOG_LEVEL as LogLevel) || 'info'

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[ENV_LOG_LEVEL]
}

function formatMessage(level: LogLevel, context: string, message: string, ...args: unknown[]): string {
  const timestamp = new Date().toISOString()
  const formattedArgs = args.length > 0 ? ' ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ') : ''
  return `[${timestamp}] [${level.toUpperCase()}] [${context}] ${message}${formattedArgs}`
}

export function createLogger(context: string) {
  return {
    debug: (message: string, ...args: unknown[]) => {
      if (shouldLog('debug')) {
        console.debug(formatMessage('debug', context, message, ...args))
      }
    },
    info: (message: string, ...args: unknown[]) => {
      if (shouldLog('info')) {
        console.info(formatMessage('info', context, message, ...args))
      }
    },
    warn: (message: string, ...args: unknown[]) => {
      if (shouldLog('warn')) {
        console.warn(formatMessage('warn', context, message, ...args))
      }
    },
    error: (message: string, ...args: unknown[]) => {
      if (shouldLog('error')) {
        console.error(formatMessage('error', context, message, ...args))
      }
    },
  }
}

export const logger = createLogger('app')
