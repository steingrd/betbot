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
  onCommand: (command: string, args: string) => void
}

export function ChatPanel({ messages, connected, streaming, onSend, onCommand }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="divide-y">
          {messages.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              <p className="text-lg font-medium mb-2">Velkommen til BetBot</p>
              <p className="text-sm">
                Skriv en melding for a chatte med AI-assistenten, eller bruk /kommandoer:
              </p>
              <div className="mt-4 text-sm text-left max-w-xs mx-auto space-y-1">
                <p><code className="bg-muted px-1 rounded">/download</code> - Last ned data</p>
                <p><code className="bg-muted px-1 rounded">/train</code> - Tren modeller</p>
                <p><code className="bg-muted px-1 rounded">/predict</code> - Finn value bets</p>
                <p><code className="bg-muted px-1 rounded">/results</code> - Siste resultater</p>
              </div>
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
          onCommand={onCommand}
          disabled={!connected || streaming}
        />
        {!connected && (
          <p className="text-xs text-destructive mt-1">Kobler til...</p>
        )}
      </div>
    </div>
  )
}
