// 统一前端日志出口：console 与诊断落盘共用同一份脱敏结果。
// 任何输入都不允许让日志调用本身抛错；敏感值在序列化阶段就打码。
type LogLevel = 'debug' | 'info' | 'warning' | 'error'

export type LogFields = {
  event?: string
  operationId?: string
  outcome?: string
  durationMs?: number
  data?: Record<string, unknown>
}

export interface DiagnosticsSinkEvent extends LogFields {
  v: 1
  ts: string
  level: LogLevel
  context: string
  message: string
  sessionId?: string
  args?: string[]
  error?: { name: string; message: string; stack?: string }
}

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warning: 2,
  error: 3,
}

const isLogLevel = (value: unknown): value is LogLevel =>
  typeof value === 'string' && value in LOG_LEVELS

const ENV_LOG_LEVEL = isLogLevel(import.meta.env.VITE_LOG_LEVEL)
  ? (import.meta.env.VITE_LOG_LEVEL as LogLevel)
  : 'info'

const MESSAGE_CAP = 2000
const ARG_COUNT_CAP = 6
const ARG_CAP = 500
const STACK_CAP = 1500
const DATA_DEPTH_CAP = 3
const DATA_BREADTH_CAP = 12

type DiagnosticsSink = (event: DiagnosticsSinkEvent) => void
let diagnosticsSink: DiagnosticsSink | null = null

// 仅供 diagnostics 模块在启动时注册；sink 自身抛错一律静默丢弃，绝不再走日志。
export function setDiagnosticsSink(sink: DiagnosticsSink | null): void {
  diagnosticsSink = sink
}

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[ENV_LOG_LEVEL]
}

// 逐条打码：认证头、键值对形式的密钥、URL 里的签名参数、URL userinfo、本机用户目录。
const REDACTION_PATTERNS: { pattern: RegExp; replacement: string }[] = [
  { pattern: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi, replacement: 'Bearer <redacted>' },
  { pattern: /(^|[^A-Za-z0-9])(?:api[_-]?key|apikey|secret(?:[_-]?key)?|password|authorization|access[_-]?token|auth[_-]?token|token|sig)\s*[=:]\s*["']?[A-Za-z0-9\-._/~+=]{4,}/gi, replacement: '$1<redacted-credential>' },
  { pattern: /([?&](?:access_token|auth_token|token|api_key|apikey|signature|secret|sig)=)[^&\s"']+/gi, replacement: '$1<redacted>' },
  { pattern: /\/\/[^\s/:@"']+:[^\s@]+@/g, replacement: '//<redacted>@' },
  { pattern: /([A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/])[^\s"']+/g, replacement: '$1<user>' },
]

export function redactText(value: string): string {
  let result = value
  for (const { pattern, replacement } of REDACTION_PATTERNS) {
    result = result.replace(pattern, replacement)
  }
  return result
}

function truncate(value: string, cap: number): string {
  return value.length <= cap ? value : `${value.slice(0, cap)}…<truncated>`
}

function redactValue(value: unknown, depth = 0): unknown {
  if (typeof value === 'string') return redactText(value)
  if (typeof value === 'symbol') return redactText(String(value))
  if (typeof value === 'bigint') return `${value}n`
  if (typeof value === 'function') return '[function]'
  if (value === null || typeof value !== 'object') return value
  if (depth >= DATA_DEPTH_CAP) return '[depth-limit]'
  try {
    if (value instanceof Error) return serializeError(value)
    if (Array.isArray(value)) return value.slice(0, DATA_BREADTH_CAP).map((item) => redactValue(item, depth + 1))
    return Object.fromEntries(Object.entries(value).slice(0, DATA_BREADTH_CAP).map(([key, item]) => [
      redactText(key), /token|secret|key|password|authorization/i.test(key) ? '<redacted>' : redactValue(item, depth + 1),
    ]))
  } catch {
    return '[unserializable]'
  }
}

function safeStringify(value: unknown, depth: number): string {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  const type = typeof value
  if (type === 'string') return truncate(redactText(value as string), ARG_CAP)
  if (type === 'number' || type === 'boolean') return String(value)
  if (type === 'bigint') return `${value}n`
  if (type === 'function') return '[function]'
  if (type === 'symbol') return (value as symbol).toString()
  if (depth >= DATA_DEPTH_CAP) return '[depth-limit]'
  try {
    if (Array.isArray(value)) {
      return `[${value.slice(0, DATA_BREADTH_CAP).map((item) => safeStringify(item, depth + 1)).join(', ')}${value.length > DATA_BREADTH_CAP ? ', …' : ''}]`
    }
    if (value instanceof Error) return safeStringify(serializeError(value), depth + 1)
    const entries = Object.entries(value as Record<string, unknown>).slice(0, DATA_BREADTH_CAP)
      .map(([key, item]) => `${redactText(key)}: ${/token|secret|key|password|authorization/i.test(key) ? '<redacted>' : safeStringify(item, depth + 1)}`)
    return `{${entries.join(', ')}}`
  } catch {
    return '[unserializable]'
  }
}

function serializeError(error: Error): { name: string; message: string; stack?: string } {
  const result: { name: string; message: string; stack?: string } = {
    name: truncate(redactText(error.name || 'Error'), 100),
    message: truncate(redactText(error.message || ''), MESSAGE_CAP),
  }
  if (error.stack) result.stack = truncate(redactText(error.stack), STACK_CAP)
  return result
}

// 兼容现有 `%s` 风格调用：占位符依次吃掉字符串化参数，剩余参数按旧格式追加。
function interpolate(message: string, args: string[]): string {
  let index = 0
  const replaced = message.replace(/%[sdj]/g, (token) => {
    if (index >= args.length) return token
    const arg = args[index++]
    return token === '%d' ? String(Number(arg) || arg) : arg
  })
  const leftover = args.slice(index)
  return leftover.length > 0 ? `${replaced} ${leftover.join(' ')}` : replaced
}

function serializeArgs(args: unknown[]): string[] {
  return args.slice(0, ARG_COUNT_CAP).map((arg) => safeStringify(redactValue(arg), 0))
}

function printToConsole(level: LogLevel, line: string): void {
  if (level === 'error') console.error(line)
  else if (level === 'warning') console.warn(line)
  else if (level === 'debug') console.debug(line)
  else console.info(line)
}

export interface Logger {
  debug: (message: string, ...args: unknown[]) => void
  info: (message: string, ...args: unknown[]) => void
  warn: (message: string, ...args: unknown[]) => void
  error: (message: string, ...args: unknown[]) => void
  child: (fields: LogFields) => Logger
}

function emit(level: LogLevel, context: string, baseFields: LogFields, message: string, args: unknown[]): void {
  if (!shouldLog(level)) return
  const argTexts = serializeArgs(args)
  const timestamp = new Date().toISOString().replace(/\.000Z$/, '')
  printToConsole(level, redactText(`[${timestamp}] [${level.toUpperCase()}] [${context}] - ${interpolate(redactText(message), argTexts)}`))

  if (!diagnosticsSink) return
  try {
    const firstError = args.find((arg): arg is Error => arg instanceof Error)
    const event: DiagnosticsSinkEvent = {
      v: 1,
      ts: new Date().toISOString(),
      level,
      context: truncate(redactText(context), 200),
      message: truncate(redactText(message), MESSAGE_CAP),
      ...(redactValue(baseFields) as LogFields),
    }
    if (argTexts.length > 0) event.args = argTexts
    if (firstError) event.error = serializeError(firstError)
    diagnosticsSink(event)
  } catch {
    // 诊断链路的问题不允许反过来干扰业务。
  }
}

function createLoggerWithContext(context: string, baseFields: LogFields): Logger {
  return {
    debug: (message, ...args) => emit('debug', context, baseFields, message, args),
    info: (message, ...args) => emit('info', context, baseFields, message, args),
    warn: (message, ...args) => emit('warning', context, baseFields, message, args),
    error: (message, ...args) => emit('error', context, baseFields, message, args),
    child: (fields) => createLoggerWithContext(context, { ...baseFields, ...fields }),
  }
}

export function createLogger(context: string, fields?: LogFields): Logger {
  return createLoggerWithContext(context, fields ?? {})
}

export const logger = createLogger('app')
