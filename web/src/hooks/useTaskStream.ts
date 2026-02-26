import { useCallback, useRef, useState } from 'react'
import type { TaskProgress } from '@/types'

interface TaskState {
  taskId: string | null
  type: string | null
  progress: TaskProgress | null
  finished: boolean
  error: string | null
  result: Record<string, unknown> | null
}

export function useTaskStream() {
  const [state, setState] = useState<TaskState>({
    taskId: null,
    type: null,
    progress: null,
    finished: false,
    error: null,
    result: null,
  })
  const sourceRef = useRef<EventSource | null>(null)

  const startStream = useCallback((taskId: string, taskType: string) => {
    // Close existing stream
    sourceRef.current?.close()

    setState({
      taskId,
      type: taskType,
      progress: null,
      finished: false,
      error: null,
      result: null,
    })

    const source = new EventSource(`/api/tasks/${taskId}/stream`)
    sourceRef.current = source

    source.addEventListener('progress', (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      setState((prev) => ({ ...prev, progress: data }))
    })

    source.addEventListener('finished', (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      setState((prev) => ({
        ...prev,
        finished: true,
        result: data,
        progress: null,
      }))
      source.close()
    })

    source.addEventListener('error', (e) => {
      // SSE error event - check if it's a server-sent error or connection error
      if (e instanceof MessageEvent) {
        const data = JSON.parse(e.data)
        setState((prev) => ({
          ...prev,
          error: data.message || 'Unknown error',
          progress: null,
        }))
      } else {
        // Connection error
        setState((prev) => ({
          ...prev,
          error: 'Connection lost',
          progress: null,
        }))
      }
      source.close()
    })
  }, [])

  const clear = useCallback(() => {
    sourceRef.current?.close()
    setState({
      taskId: null,
      type: null,
      progress: null,
      finished: false,
      error: null,
      result: null,
    })
  }, [])

  return { ...state, startStream, clear }
}
