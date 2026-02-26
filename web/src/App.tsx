import { useCallback, useRef, useState } from 'react'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { DataQualityCard } from '@/components/dashboard/DataQualityCard'
import { ActivityIndicator } from '@/components/dashboard/ActivityIndicator'
import { EventLog, type LogEntry } from '@/components/dashboard/EventLog'
import { PredictionsTable } from '@/components/predictions/PredictionsTable'
import { useChat } from '@/hooks/useChat'
import { useTaskStream } from '@/hooks/useTaskStream'
import { useDataStatus } from '@/hooks/useDataStatus'
import { api } from '@/lib/api'
import type { Prediction } from '@/types'
import { Circle } from 'lucide-react'

let logId = 0

function App() {
  const chat = useChat()
  const task = useTaskStream()
  const { status, loading: statusLoading, refresh: refreshStatus } = useDataStatus()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const predictionsRef = useRef(predictions)
  predictionsRef.current = predictions

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    const now = new Date()
    const time = now.toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs((prev) => [...prev.slice(-99), { id: `log-${++logId}`, time, message, level }])
  }, [])

  const handleCommand = useCallback(
    async (command: string, args: string) => {
      if (command === 'help') {
        chat.addSystemMessage(
          '**Tilgjengelige kommandoer:**\n' +
          '- `/download` - Last ned data fra FootyStats\n' +
          '- `/download full` - Last ned all data\n' +
          '- `/train` - Tren ML-modeller\n' +
          '- `/predict` - Finn value bets\n' +
          '- `/results` - Vis nyeste kampresultater\n' +
          '- `/status` - Oppdater status\n' +
          '- `/clear` - Nullstill chat-historikk'
        )
        return
      }

      if (command === 'clear') {
        try {
          await api.clearChatHistory()
          window.location.reload()
        } catch {
          addLog('Kunne ikke nullstille chat', 'error')
        }
        return
      }

      if (command === 'status') {
        refreshStatus()
        addLog('Status oppdatert', 'info')
        return
      }

      if (command === 'results') {
        try {
          const results = await api.getResults()
          if (results.length === 0) {
            chat.addSystemMessage('Ingen ferdigspilte kamper funnet.')
            return
          }
          const header = '| Dato | Liga | Hjemme | | | Borte |\n|------|------|--------|---|---|------|\n'
          const rows = results
            .map((r) => `| ${r.date} | ${r.league || ''} | ${r.home_team} | ${r.home_goals} | ${r.away_goals} | ${r.away_team} |`)
            .join('\n')
          chat.addSystemMessage(header + rows)
        } catch {
          addLog('Kunne ikke hente resultater', 'error')
        }
        return
      }

      // Long-running tasks
      if (['download', 'train', 'predict'].includes(command)) {
        try {
          let result
          if (command === 'download') {
            const full = args.trim().toLowerCase() === 'full'
            result = await api.startDownload(full)
            addLog(`Starter nedlasting${full ? ' (full)' : ''}...`, 'info')
          } else if (command === 'train') {
            result = await api.startTraining()
            addLog('Starter trening...', 'info')
          } else {
            result = await api.startPredictions()
            addLog('Starter predictions...', 'info')
          }
          task.startStream(result.task_id, result.task_type)
        } catch (e) {
          addLog(`Feil: ${e instanceof Error ? e.message : 'ukjent feil'}`, 'error')
        }
        return
      }

      chat.addSystemMessage(`Ukjent kommando: /${command}`)
    },
    [chat, task, addLog, refreshStatus]
  )

  // Handle task completion side effects
  const prevFinishedRef = useRef(false)
  if (task.finished && !prevFinishedRef.current) {
    prevFinishedRef.current = true
    refreshStatus()

    if (task.type === 'download' && task.result) {
      const r = task.result as { ok: number; skipped: number; matches: number; failed: number }
      addLog(`Nedlasting ferdig: ${r.ok} sesonger, ${r.matches} kamper`, 'success')
    } else if (task.type === 'train' && task.result) {
      addLog('Trening fullfort', 'success')
    } else if (task.type === 'predict' && task.result) {
      const r = task.result as { picks: Prediction[]; match_count: number; stale_warning?: string }
      setPredictions(r.picks || [])
      if (r.picks?.length) {
        addLog(`Fant ${r.picks.length} value bets fra ${r.match_count} kamper`, 'success')
        // Render predictions inline in chat
        const header = '| Tid | Kamp | Market | Modell | Edge | Konf. |\n|-----|------|--------|--------|------|-------|\n'
        const rows = r.picks
          .map(
            (p: Prediction) =>
              `| ${p.kickoff} | ${p.home_team} vs ${p.away_team} | ${p.market} | ${p.model_prob != null ? (p.model_prob * 100).toFixed(1) + '%' : '-'} | ${p.edge != null ? (p.edge * 100).toFixed(1) + '%' : '-'} | ${p.confidence} |`
          )
          .join('\n')
        chat.addSystemMessage(`**Value bets funnet:**\n\n${header}${rows}`)
      } else {
        addLog(`Ingen value bets funnet (${r.match_count} kamper analysert)`, 'info')
        chat.addSystemMessage('Ingen value bets funnet.')
      }
      if (r.stale_warning) {
        addLog(r.stale_warning, 'warning')
      }
    }

    // Auto-clear task state after showing result
    setTimeout(() => {
      task.clear()
      prevFinishedRef.current = false
    }, 2000)
  }
  if (task.error && prevFinishedRef.current === false) {
    // Reset on new task
  }
  if (!task.taskId) {
    prevFinishedRef.current = false
  }

  // Log task progress
  const prevProgressRef = useRef<string | null>(null)
  if (task.progress && task.progress.detail !== prevProgressRef.current) {
    prevProgressRef.current = task.progress.detail
    addLog(task.progress.detail, 'info')
  }

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

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="border-b px-4 py-2 flex items-center gap-2 shrink-0">
        <span className="font-bold text-lg">BetBot</span>
        <span className="text-muted-foreground text-sm">Value Bet Analysis</span>
        <div className="flex-1" />
        <Circle
          className={`h-2.5 w-2.5 ${chat.connected ? 'fill-green-500 text-green-500' : 'fill-red-500 text-red-500'}`}
        />
      </header>
      <main className="flex-1 flex overflow-hidden">
        {/* Chat - left panel */}
        <div className="flex-1 min-w-0">
          <ChatPanel
            messages={chat.messages}
            connected={chat.connected}
            streaming={chat.streaming}
            onSend={chat.sendMessage}
            onCommand={handleCommand}
          />
        </div>

        {/* Sidebar - right panel */}
        <aside className="w-72 border-l flex flex-col gap-3 p-3 overflow-y-auto shrink-0">
          <DataQualityCard status={status} loading={statusLoading} />
          <ActivityIndicator
            taskId={task.taskId}
            taskType={task.type}
            progress={task.progress}
            error={task.error}
            finished={task.finished}
            onCancel={handleCancel}
          />
          {predictions.length > 0 && <PredictionsTable predictions={predictions} />}
          <EventLog entries={logs} />
        </aside>
      </main>
    </div>
  )
}

export default App
