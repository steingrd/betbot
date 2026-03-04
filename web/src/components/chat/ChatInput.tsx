import { useState, useRef, useCallback } from 'react'
import { Input } from '@/components/ui/input'
import { Send } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = useCallback(() => {
    const text = value.trim()
    if (!text) return
    onSend(text)
    setValue('')
  }, [value, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex gap-2">
      <Input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Still et sporsmal..."
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
  )
}
