import { useLocation, useNavigate } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PredictionsCard } from './PredictionsCard'
import { SafePicksCard } from './SafePicksCard'
import { ConfidentGoalsCard } from './ConfidentGoalsCard'
import { ResultsCard } from '@/components/dashboard/ResultsCard'
import { CouponsCard } from '@/components/bets/CouponsCard'
import type { Accumulator, BetRecord, ConfidentGoalPick, MatchResult, PlacedBetRef, Prediction, SafePick } from '@/types'

const TAB_ROUTES: Record<string, string> = {
  '/': 'value-bets',
  '/kombispill': 'kombispill',
  '/btts': 'btts',
  '/kuponger': 'kuponger',
  '/resultater': 'resultater',
}

const ROUTE_FOR_TAB: Record<string, string> = Object.fromEntries(
  Object.entries(TAB_ROUTES).map(([path, tab]) => [tab, path])
)

interface Props {
  predictions: Prediction[]
  safePicks: SafePick[]
  accumulators: Accumulator[]
  confidentGoals: ConfidentGoalPick[]
  predictionsLoading: boolean
  results: MatchResult[]
  resultsLoading: boolean
  placedIds?: PlacedBetRef[]
  bets?: BetRecord[]
  betsLoading?: boolean
  onPredictionClick?: (prediction: Prediction) => void
  onAccumulatorClick?: (accumulator: Accumulator) => void
  onCancelBet?: (id: number) => void
}

export function PredictionsTabs({
  predictions,
  safePicks,
  accumulators,
  confidentGoals,
  predictionsLoading,
  results,
  resultsLoading,
  placedIds,
  bets = [],
  betsLoading = false,
  onPredictionClick,
  onAccumulatorClick,
  onCancelBet,
}: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const activeTab = TAB_ROUTES[location.pathname] ?? 'value-bets'

  return (
    <Tabs value={activeTab} onValueChange={(tab) => navigate(ROUTE_FOR_TAB[tab] ?? '/')}>
      <TabsList>
        <TabsTrigger value="value-bets">Value Bets</TabsTrigger>
        <TabsTrigger value="kombispill">Kombispill</TabsTrigger>
        <TabsTrigger value="btts">BTTS / O2.5</TabsTrigger>
        <TabsTrigger value="kuponger">Kuponger</TabsTrigger>
        <TabsTrigger value="resultater">Resultater</TabsTrigger>
      </TabsList>
      <TabsContent value="value-bets">
        <PredictionsCard
          predictions={predictions}
          loading={predictionsLoading}
          placedIds={placedIds}
          onRowClick={onPredictionClick}
        />
      </TabsContent>
      <TabsContent value="kombispill">
        <SafePicksCard
          safePicks={safePicks}
          accumulators={accumulators}
          loading={predictionsLoading}
          placedIds={placedIds}
          onAccumulatorClick={onAccumulatorClick}
        />
      </TabsContent>
      <TabsContent value="btts">
        <ConfidentGoalsCard confidentGoals={confidentGoals} loading={predictionsLoading} />
      </TabsContent>
      <TabsContent value="kuponger">
        <CouponsCard bets={bets} loading={betsLoading} onCancel={onCancelBet ?? (() => {})} />
      </TabsContent>
      <TabsContent value="resultater">
        <ResultsCard results={results} loading={resultsLoading} />
      </TabsContent>
    </Tabs>
  )
}
