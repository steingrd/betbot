import { useState, useRef, useCallback } from 'react'
import { Input } from '@/components/ui/input'
import { Send } from 'lucide-react'

const COMMANDS = [
  { name: '/download', desc: 'Last ned data fra FootyStats' },
  { name: '/download full', desc: 'Last ned all data (inkl. ferdige sesonger)' },
  { name: '/train', desc: 'Tren ML-modeller' },
  { name: '/predict', desc: 'Finn value bets' },
  { name: '/results', desc: 'Vis nyeste kampresultater' },
  { name: '/status', desc: 'Oppdater status' },
  { name: '/clear', desc: 'Nullstill chat-historikk' },
  { name: '/help', desc: 'Vis tilgjengelige kommandoer' },
]

interface Props {
  onSend: (text: string) => void
  onCommand: (command: string, args: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, onCommand, disabled }: Props) {
  const [value, setValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const suggestions = value.startsWith('/')
    ? COMMANDS.filter((c) => c.name.startsWith(value))
    : []

  const handleSubmit = useCallback(() => {
    const text = value.trim()
    if (!text) return

    if (text.startsWith('/')) {
      const parts = text.slice(1).split(/\s+/, 2)
      const cmd = parts[0]
      const args = parts[1] || ''
      onCommand(cmd, args)
    } else {
      onSend(text)
    }

    setValue('')
    setShowSuggestions(false)
  }, [value, onSend, onCommand])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  return (
    <div className="relative">
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 bg-popover border rounded-md shadow-md mb-1 max-h-48 overflow-y-auto z-10">
          {suggestions.map((cmd) => (
            <button
              key={cmd.name}
              className="w-full text-left px-3 py-2 text-sm hover:bg-accent flex justify-between gap-4"
              onMouseDown={(e) => {
                e.preventDefault()
                setValue(cmd.name + ' ')
                inputRef.current?.focus()
                setShowSuggestions(false)
              }}
            >
              <span className="font-mono font-medium">{cmd.name}</span>
              <span className="text-muted-foreground">{cmd.desc}</span>
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setShowSuggestions(e.target.value.startsWith('/'))
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (value.startsWith('/')) setShowSuggestions(true)
          }}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
          placeholder="Skriv melding eller /kommando..."
          disabled={disabled}
          className="flex-1"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="px-3 text-muted-foreground hover:text-foreground disabled:opacity-30"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
