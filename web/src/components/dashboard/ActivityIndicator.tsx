import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Loader2, X } from 'lucide-react'
import type { TaskProgress } from '@/types'

interface Props {
  taskId: string | null
  taskType: string | null
  progress: TaskProgress | null
  error: string | null
  finished: boolean
  onCancel: () => void
}

export function ActivityIndicator({ taskId, taskType: _taskType, progress, error, finished, onCancel }: Props) {
  const isActive = taskId && !finished && !error

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Aktivitet</CardTitle>
          {isActive && (
            <Button variant="ghost" size="icon" className="h-5 w-5" onClick={onCancel}>
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isActive && progress ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <span className="font-medium">{progress.step}</span>
            </div>
            <p className="text-xs text-muted-foreground">{progress.detail}</p>
            {progress.percent != null && (
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
            )}
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : (
          <p className="text-sm text-muted-foreground">Ingen aktiv oppgave</p>
        )}
      </CardContent>
    </Card>
  )
}
