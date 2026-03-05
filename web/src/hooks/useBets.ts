import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { BetInput, BetRecord, BetSummary, PlacedBetRef } from '@/types'

export function useBets() {
  const [summary, setSummary] = useState<BetSummary | null>(null)
  const [bets, setBets] = useState<BetRecord[]>([])
  const [placedIds, setPlacedIds] = useState<PlacedBetRef[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const [s, b, p] = await Promise.all([
        api.getBetSummary(),
        api.getBets(),
        api.getPlacedIds(),
      ])
      setSummary(s)
      setBets(b)
      setPlacedIds(p)
    } catch {
      // silent fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const placeBet = useCallback(async (bet: BetInput) => {
    const result = await api.placeBet(bet)
    await refresh()
    return result
  }, [refresh])

  const cancelBet = useCallback(async (id: number) => {
    await api.cancelBet(id)
    await refresh()
  }, [refresh])

  return { summary, bets, placedIds, loading, refresh, placeBet, cancelBet }
}
