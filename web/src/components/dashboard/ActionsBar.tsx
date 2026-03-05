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

export function ActionButtons({
  taskId,
  taskType,
  finished,
  error,
  onDownload,
  onTrain,
  onPredict,
}: Pick<Props, 'taskId' | 'taskType' | 'finished' | 'error' | 'onDownload' | 'onTrain' | 'onPredict'>) {
  const busy = !!taskId && !finished && !error

  return (
    <div className="flex gap-1.5">
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
        Last ned
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
        Tren
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
        Predict
      </Button>
    </div>
  )
}

export function TaskProgressBar({
  taskId,
  progress,
  error,
  finished,
  onCancel,
}: Pick<Props, 'taskId' | 'progress' | 'error' | 'finished' | 'onCancel'>) {
  const busy = !!taskId && !finished && !error

  if (!busy || !progress) return null

  return (
    <div className="border-b px-4 py-1.5 space-y-1 bg-muted/30">
      {progress.percent != null && (
        <Progress value={progress.percent} className="h-1.5" />
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
  )
}

// Keep backward compat export
export function ActionsBar(props: Props) {
  return (
    <div className="space-y-2">
      <ActionButtons {...props} />
      <TaskProgressBar {...props} />
      {props.error && (
        <p className="text-xs text-destructive">{props.error}</p>
      )}
    </div>
  )
}
