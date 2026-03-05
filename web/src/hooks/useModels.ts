import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { ModelInfo } from '@/types'

export function useModels() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [activeSlug, setActiveSlug] = useState('standard')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [modelList, active] = await Promise.all([
        api.getModels(),
        api.getActiveModel(),
      ])
      setModels(modelList)
      setActiveSlug(active.slug)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const setActive = useCallback(async (slug: string) => {
    await api.setActiveModel(slug)
    setActiveSlug(slug)
  }, [])

  const createModel = useCallback(async (data: { name: string; strategies: string[]; years?: number | null }) => {
    const model = await api.createModel(data)
    await refresh()
    return model
  }, [refresh])

  const deleteModel = useCallback(async (slug: string) => {
    await api.deleteModel(slug)
    await refresh()
  }, [refresh])

  return { models, activeSlug, loading, refresh, setActive, createModel, deleteModel }
}
