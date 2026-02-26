import { useCallback, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '@/types'

let nextId = 0
function makeId() {
  return `msg-${++nextId}-${Date.now()}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [connected, setConnected] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const currentAssistantIdRef = useRef<string | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`)

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setStreaming(false)
      // Reconnect after delay
      setTimeout(connect, 3000)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'token') {
        setStreaming(true)
        if (!currentAssistantIdRef.current) {
          const id = makeId()
          currentAssistantIdRef.current = id
          setMessages((prev) => [
            ...prev,
            { id, role: 'assistant', content: data.content, streaming: true },
          ])
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === currentAssistantIdRef.current
                ? { ...m, content: m.content + data.content }
                : m
            )
          )
        }
      } else if (data.type === 'done') {
        setStreaming(false)
        if (currentAssistantIdRef.current) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === currentAssistantIdRef.current
                ? { ...m, content: data.content, streaming: false }
                : m
            )
          )
          currentAssistantIdRef.current = null
        }
      } else if (data.type === 'error') {
        setStreaming(false)
        currentAssistantIdRef.current = null
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: 'system', content: `Feil: ${data.content}` },
        ])
      }
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

    const id = makeId()
    setMessages((prev) => [...prev, { id, role: 'user', content: text }])
    wsRef.current.send(JSON.stringify({ type: 'message', content: text }))
  }, [])

  const addSystemMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: 'system', content: text }])
  }, [])

  return { messages, connected, streaming, sendMessage, addSystemMessage }
}
