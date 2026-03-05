import { useCallback, useRef, useState } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { StatusMetricsRow } from '@/components/dashboard/StatusMetricsRow'
import { ActionButtons, TaskProgressBar } from '@/components/dashboard/ActionsBar'
import { PredictionsTabs } from '@/components/predictions/PredictionsTabs'
import { BetModal } from '@/components/bets/BetModal'
import { ModelSelector } from '@/components/models/ModelSelector'
import { useChat } from '@/hooks/useChat'
import { useModels } from '@/hooks/useModels'
import { useTaskStream } from '@/hooks/useTaskStream'
import { useDataStatus } from '@/hooks/useDataStatus'
import { useResults } from '@/hooks/useResults'
import { usePredictions } from '@/hooks/usePredictions'
import { useBets } from '@/hooks/useBets'
import { api } from '@/lib/api'
import type { Accumulator, ConfidentGoalPick, Prediction, SafePick } from '@/types'
import { Circle, MessageSquare } from 'lucide-react'

interface LogEntry {
  id: string
  time: string
  message: string
  level: 'info' | 'success' | 'warning' | 'error'
}

let logId = 0

function App() {
  const chat = useChat()
  const task = useTaskStream()
  const { models, activeSlug, setActive, createModel, deleteModel, refresh: refreshModels } = useModels()
  const { status, loading: statusLoading, refresh: refreshStatus } = useDataStatus()
  const { results, loading: resultsLoading, refresh: refreshResults } = useResults()
  const {
    predictions,
    setPredictions,
    safePicks,
    setSafePicks,
    accumulators,
    setAccumulators,
    confidentGoals,
    setConfidentGoals,
    loading: predictionsLoading,
    refresh: refreshPredictions,
  } = usePredictions()
  const { summary: betSummary, bets, placedIds, loading: betsLoading, refresh: refreshBets, placeBet, cancelBet } = useBets()
  const [, setLogs] = useState<LogEntry[]>([])
  const [chatOpen, setChatOpen] = useState(false)
  const [betModalOpen, setBetModalOpen] = useState(false)
  const [selectedPrediction, setSelectedPrediction] = useState<Prediction | null>(null)
  const [selectedAccumulator, setSelectedAccumulator] = useState<Accumulator | null>(null)

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    const now = new Date()
    const time = now.toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs((prev) => [...prev.slice(-99), { id: `log-${++logId}`, time, message, level }])
  }, [])

  // Action handlers
  const handleDownload = useCallback(async () => {
    try {
      const result = await api.startDownload(false)
      addLog('Starter nedlasting...', 'info')
      task.startStream(result.task_id, result.task_type)
    } catch (e) {
      addLog(`Feil: ${e instanceof Error ? e.message : 'ukjent feil'}`, 'error')
    }
  }, [task, addLog])

  const handleTrain = useCallback(async () => {
    try {
      const result = await api.startTraining(activeSlug)
      addLog(`Starter trening (${activeSlug})...`, 'info')
      task.startStream(result.task_id, result.task_type)
    } catch (e) {
      addLog(`Feil: ${e instanceof Error ? e.message : 'ukjent feil'}`, 'error')
    }
  }, [task, addLog, activeSlug])

  const handlePredict = useCallback(async () => {
    try {
      const result = await api.startPredictions(activeSlug)
      addLog('Starter predictions...', 'info')
      task.startStream(result.task_id, result.task_type)
    } catch (e) {
      addLog(`Feil: ${e instanceof Error ? e.message : 'ukjent feil'}`, 'error')
    }
  }, [task, addLog, activeSlug])

  const handleCancel = useCallback(async () => {
    if (task.taskId) {
      try {
        await api.cancelTask(task.taskId)
        addLog('Oppgave avbrutt', 'warning')
        task.clear()
      } catch {
        addLog('Kunne ikke avbryte oppgave', 'error')
      }
    }
  }, [task, addLog])

  // Handle task completion side effects
  const prevFinishedRef = useRef(false)
  if (task.finished && !prevFinishedRef.current) {
    prevFinishedRef.current = true
    refreshStatus()
    refreshResults()
    refreshPredictions()
    refreshBets()
    refreshModels()

    if (task.type === 'download' && task.result) {
      const r = task.result as { ok: number; skipped: number; matches: number; failed: number }
      addLog(`Nedlasting ferdig: ${r.ok} sesonger, ${r.matches} kamper`, 'success')
    } else if (task.type === 'train' && task.result) {
      addLog('Trening fullfort', 'success')
    } else if (task.type === 'predict' && task.result) {
      const r = task.result as {
        picks: Prediction[]
        match_count: number
        stale_warning?: string
        safe_picks?: SafePick[]
        accumulators?: Accumulator[]
        confident_goals?: ConfidentGoalPick[]
      }
      setPredictions(r.picks || [])
      setSafePicks(r.safe_picks || [])
      setAccumulators(r.accumulators || [])
      setConfidentGoals(r.confident_goals || [])
      if (r.picks?.length) {
        addLog(`Fant ${r.picks.length} value bets fra ${r.match_count} kamper`, 'success')
      } else {
        addLog(`Ingen value bets funnet (${r.match_count} kamper analysert)`, 'info')
      }
    }

    setTimeout(() => {
      task.clear()
      prevFinishedRef.current = false
    }, 2000)
  }
  if (!task.taskId) {
    prevFinishedRef.current = false
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        {/* Header with action buttons */}
        <header className="border-b px-4 py-2.5 flex items-center gap-2 sticky top-0 bg-background/95 backdrop-blur z-40">
          <span className="font-bold text-lg">BetBot</span>
          <Circle
            className={`h-2 w-2 ${chat.connected ? 'fill-green-500 text-green-500' : 'fill-red-500 text-red-500'}`}
          />
          <div className="flex-1" />
          <ModelSelector
            models={models}
            activeSlug={activeSlug}
            onSelect={setActive}
            onCreate={createModel}
            onDelete={deleteModel}
          />
          <ActionButtons
            taskId={task.taskId}
            taskType={task.type}
            finished={task.finished}
            error={task.error}
            onDownload={handleDownload}
            onTrain={handleTrain}
            onPredict={handlePredict}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => setChatOpen(true)}
          >
            <MessageSquare className="h-4 w-4" />
            Chat
          </Button>
        </header>

        {/* Progress bar under header */}
        <TaskProgressBar
          taskId={task.taskId}
          progress={task.progress}
          error={task.error}
          finished={task.finished}
          onCancel={handleCancel}
        />

        {task.error && (
          <div className="px-4 py-1.5 bg-destructive/10 border-b">
            <p className="text-xs text-destructive">{task.error}</p>
          </div>
        )}

        {/* Dashboard content */}
        <div className="px-6 py-4 space-y-4">
          {/* Status metrics */}
          <StatusMetricsRow status={status} loading={statusLoading} betSummary={betSummary} betLoading={betsLoading} />

          {/* Predictions tabs */}
          <PredictionsTabs
            predictions={predictions}
            safePicks={safePicks}
            accumulators={accumulators}
            confidentGoals={confidentGoals}
            predictionsLoading={predictionsLoading}
            results={results}
            resultsLoading={resultsLoading}
            placedIds={placedIds}
            bets={bets}
            betsLoading={betsLoading}
            onPredictionClick={(p) => {
              setSelectedPrediction(p)
              setSelectedAccumulator(null)
              setBetModalOpen(true)
            }}
            onAccumulatorClick={(a) => {
              setSelectedAccumulator(a)
              setSelectedPrediction(null)
              setBetModalOpen(true)
            }}
            onCancelBet={cancelBet}
          />
        </div>

        {/* Bet Modal */}
        <BetModal
          open={betModalOpen}
          onOpenChange={setBetModalOpen}
          onPlace={placeBet}
          prediction={selectedPrediction}
          accumulator={selectedAccumulator}
        />

        {/* Chat Sheet */}
        <Sheet open={chatOpen} onOpenChange={setChatOpen}>
          <SheetContent side="right" className="w-full sm:max-w-lg p-0 gap-0">
            <SheetHeader className="px-4 pt-4 pb-2 border-b shrink-0">
              <SheetTitle>Chat</SheetTitle>
              <SheetDescription>
                Still sporsmal om modellen, data eller value bets.
              </SheetDescription>
            </SheetHeader>
            <div className="flex-1 min-h-0">
              <ChatPanel
                messages={chat.messages}
                connected={chat.connected}
                streaming={chat.streaming}
                onSend={chat.sendMessage}
              />
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  )
}

export default App
