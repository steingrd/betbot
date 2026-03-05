import type { AllPredictions, BetInput, BetRecord, BetSummary, DataStatus, MatchResult, ModelInfo, PlacedBetRef, Prediction, TaskStarted } from '@/types'

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
  getAllPredictions: () => fetchJSON<AllPredictions>('/api/predictions/all'),

  startDownload: (full = false) =>
    fetchJSON<TaskStarted>(`/api/tasks/download?full=${full}`, { method: 'POST' }),
  startTraining: (modelSlug?: string) =>
    fetchJSON<TaskStarted>(`/api/tasks/train${modelSlug ? `?model_slug=${modelSlug}` : ''}`, { method: 'POST' }),
  startPredictions: (modelSlug?: string) =>
    fetchJSON<TaskStarted>(`/api/tasks/predict${modelSlug ? `?model_slug=${modelSlug}` : ''}`, { method: 'POST' }),
  cancelTask: (taskId: string) =>
    fetchJSON<{ status: string }>(`/api/tasks/${taskId}`, { method: 'DELETE' }),

  getChatHistory: (limit = 20) =>
    fetchJSON<{ role: string; content: string }[]>(`/api/chat/history?limit=${limit}`),
  clearChatHistory: () =>
    fetchJSON<{ status: string }>('/api/chat/history', { method: 'DELETE' }),

  // Bets
  placeBet: (bet: BetInput) =>
    fetchJSON<{ id: number }>('/api/bets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bet),
    }),
  getBets: (status?: string, limit = 50) =>
    fetchJSON<BetRecord[]>(`/api/bets?${new URLSearchParams({ ...(status ? { status } : {}), limit: String(limit) })}`),
  getBetSummary: () => fetchJSON<BetSummary>('/api/bets/summary'),
  getPlacedIds: () => fetchJSON<PlacedBetRef[]>('/api/bets/placed-ids'),
  cancelBet: (id: number) =>
    fetchJSON<{ status: string }>(`/api/bets/${id}`, { method: 'DELETE' }),

  // Models
  getModels: () => fetchJSON<ModelInfo[]>('/api/models'),
  getActiveModel: () => fetchJSON<{ slug: string }>('/api/models/active'),
  setActiveModel: (slug: string) =>
    fetchJSON<{ slug: string }>(`/api/models/active?slug=${slug}`, { method: 'PUT' }),
  createModel: (data: { name: string; strategies: string[]; years?: number | null }) =>
    fetchJSON<ModelInfo>('/api/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  deleteModel: (slug: string) =>
    fetchJSON<{ status: string }>(`/api/models/${slug}`, { method: 'DELETE' }),
}
