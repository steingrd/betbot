import type { DataStatus, MatchResult, Prediction, TaskStarted } from '@/types'

const BASE = ''

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options)
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  getDataStatus: () => fetchJSON<DataStatus>('/api/data/status'),
  getResults: (limit = 20) => fetchJSON<MatchResult[]>(`/api/data/results?limit=${limit}`),
  getPredictions: () => fetchJSON<Prediction[]>('/api/predictions/latest'),

  startDownload: (full = false) =>
    fetchJSON<TaskStarted>(`/api/tasks/download?full=${full}`, { method: 'POST' }),
  startTraining: () =>
    fetchJSON<TaskStarted>('/api/tasks/train', { method: 'POST' }),
  startPredictions: () =>
    fetchJSON<TaskStarted>('/api/tasks/predict', { method: 'POST' }),
  cancelTask: (taskId: string) =>
    fetchJSON<{ status: string }>(`/api/tasks/${taskId}`, { method: 'DELETE' }),

  getChatHistory: (limit = 20) =>
    fetchJSON<{ role: string; content: string }[]>(`/api/chat/history?limit=${limit}`),
  clearChatHistory: () =>
    fetchJSON<{ status: string }>('/api/chat/history', { method: 'DELETE' }),
}
