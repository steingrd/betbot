import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { MatchResult } from '@/types'

export function useResults(limit = 15) {
  const [results, setResults] = useState<MatchResult[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getResults(limit)
      setResults(data)
    } catch {
      // silent fail
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { results, loading, refresh }
}
