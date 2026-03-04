import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Accumulator, ConfidentGoalPick, Prediction, SafePick } from '@/types'

export function usePredictions() {
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [safePicks, setSafePicks] = useState<SafePick[]>([])
  const [accumulators, setAccumulators] = useState<Accumulator[]>([])
  const [confidentGoals, setConfidentGoals] = useState<ConfidentGoalPick[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getAllPredictions()
      setPredictions(data.value_bets)
      setSafePicks(data.safe_picks)
      setAccumulators(data.accumulators)
      setConfidentGoals(data.confident_goals)
    } catch {
      // silent fail - empty predictions
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return {
    predictions,
    setPredictions,
    safePicks,
    setSafePicks,
    accumulators,
    setAccumulators,
    confidentGoals,
    setConfidentGoals,
    loading,
    refresh,
  }
}
