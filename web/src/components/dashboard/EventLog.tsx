import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ChevronDown, ChevronRight } from 'lucide-react'

export interface LogEntry {
  id: string
  time: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
}

interface Props {
  entries: LogEntry[]
}

const levelColors: Record<LogEntry['level'], string> = {
  info: 'text-muted-foreground',
  success: 'text-green-600 dark:text-green-400',
  warning: 'text-yellow-600 dark:text-yellow-400',
  error: 'text-destructive',
}

export function EventLog({ entries }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <Card>
      <CardHeader
        className="pb-2 cursor-pointer select-none"
        onClick={() => setOpen(!open)}
      >
        <CardTitle className="text-sm flex items-center gap-1.5">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          Hendelser
          {entries.length > 0 && (
            <span className="text-xs font-normal text-muted-foreground">
              ({entries.length})
            </span>
          )}
        </CardTitle>
      </CardHeader>
      {open && (
        <CardContent className="p-0">
          <ScrollArea className="max-h-48 px-4 pb-4">
            {entries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Ingen hendelser</p>
            ) : (
              <div className="space-y-1">
                {entries.map((entry) => (
                  <div key={entry.id} className="text-xs flex gap-2">
                    <span className="text-muted-foreground font-mono shrink-0">
                      {entry.time}
                    </span>
                    <span className={levelColors[entry.level]}>{entry.message}</span>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      )}
    </Card>
  )
}
