import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import type { ChatMessage as ChatMessageType } from '@/types'

interface Props {
  messages: ChatMessageType[]
  connected: boolean
  streaming: boolean
  onSend: (text: string) => void
}

export function ChatPanel({ messages, connected, streaming, onSend }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ScrollArea className="flex-1 overflow-hidden" ref={scrollRef}>
        <div className="divide-y">
          {messages.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              <p className="text-lg font-medium mb-2">BetBot Chat</p>
              <p className="text-sm">
                Still sporsmal om modellen, data eller value bets.
              </p>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
        </div>
      </ScrollArea>
      <div className="border-t p-3">
        <ChatInput
          onSend={onSend}
          disabled={!connected || streaming}
        />
        {!connected && (
          <p className="text-xs text-destructive mt-1">Kobler til...</p>
        )}
      </div>
    </div>
  )
}
