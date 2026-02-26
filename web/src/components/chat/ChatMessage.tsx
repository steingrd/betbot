import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/types'

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  if (message.role === 'system') {
    return (
      <div className="px-4 py-2 text-sm text-muted-foreground italic border-l-2 border-muted ml-2">
        {message.content}
      </div>
    )
  }

  const isUser = message.role === 'user'

  return (
    <div className={cn('px-4 py-3', isUser ? 'bg-muted/50' : '')}>
      <div className="text-xs font-medium text-muted-foreground mb-1">
        {isUser ? 'Du' : 'BetBot'}
        {message.streaming && (
          <span className="ml-2 inline-block animate-pulse">...</span>
        )}
      </div>
      {isUser ? (
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
      ) : (
        <div className="text-sm prose prose-sm dark:prose-invert max-w-none prose-table:text-xs prose-td:px-2 prose-td:py-1 prose-th:px-2 prose-th:py-1">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  )
}
