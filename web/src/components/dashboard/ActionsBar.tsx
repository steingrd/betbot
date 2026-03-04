import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Download, Brain, TrendingUp, Loader2, X } from 'lucide-react'
import type { TaskProgress } from '@/types'

interface Props {
  taskId: string | null
  taskType: string | null
  progress: TaskProgress | null
  error: string | null
  finished: boolean
  onDownload: () => void
  onTrain: () => void
  onPredict: () => void
  onCancel: () => void
}

export function ActionsBar({
  taskId,
  taskType,
  progress,
  error,
  finished,
  onDownload,
  onTrain,
  onPredict,
  onCancel,
}: Props) {
  const busy = !!taskId && !finished && !error

  return (
    <div className="space-y-2">
      <div className="flex gap-2 flex-wrap">
        <Button
          variant="outline"
          size="sm"
          onClick={onDownload}
          disabled={busy}
        >
          {busy && taskType === 'download' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Last ned data
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onTrain}
          disabled={busy}
        >
          {busy && taskType === 'train' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Brain className="h-4 w-4" />
          )}
          Tren modell
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onPredict}
          disabled={busy}
        >
          {busy && taskType === 'predict' ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <TrendingUp className="h-4 w-4" />
          )}
          Finn value bets
        </Button>
      </div>

      {busy && progress && (
        <div className="space-y-1">
          {progress.percent != null && (
            <Progress value={progress.percent} className="h-2" />
          )}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="truncate">{progress.detail}</span>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onCancel}
              className="shrink-0 ml-2"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  )
}
