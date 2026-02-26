import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

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
  return (
    <Card className="flex flex-col min-h-0 flex-1">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Hendelser</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        <ScrollArea className="h-full px-4 pb-4">
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
    </Card>
  )
}
