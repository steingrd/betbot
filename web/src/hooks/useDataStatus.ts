import { useCallback, useEffect, useState } from 'react'
import type { DataStatus } from '@/types'
import { api } from '@/lib/api'

export function useDataStatus(refreshInterval = 30000) {
  const [status, setStatus] = useState<DataStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.getDataStatus()
      setStatus(data)
    } catch {
      // silently fail - status panel shows dashes
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, refreshInterval)
    return () => clearInterval(id)
  }, [refresh, refreshInterval])

  return { status, loading, refresh }
}
