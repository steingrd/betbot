import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PredictionsCard } from './PredictionsCard'
import { SafePicksCard } from './SafePicksCard'
import { ConfidentGoalsCard } from './ConfidentGoalsCard'
import { ResultsCard } from '@/components/dashboard/ResultsCard'
import type { Accumulator, ConfidentGoalPick, MatchResult, Prediction, SafePick } from '@/types'

interface Props {
  predictions: Prediction[]
  safePicks: SafePick[]
  accumulators: Accumulator[]
  confidentGoals: ConfidentGoalPick[]
  predictionsLoading: boolean
  results: MatchResult[]
  resultsLoading: boolean
}

export function PredictionsTabs({
  predictions,
  safePicks,
  accumulators,
  confidentGoals,
  predictionsLoading,
  results,
  resultsLoading,
}: Props) {
  return (
    <Tabs defaultValue="value-bets">
      <TabsList>
        <TabsTrigger value="value-bets">
          Value Bets
          {predictions.length > 0 && (
            <span className="ml-1 text-xs text-muted-foreground">({predictions.length})</span>
          )}
        </TabsTrigger>
        <TabsTrigger value="kombispill">
          Kombispill
          {accumulators.length > 0 && (
            <span className="ml-1 text-xs text-muted-foreground">({accumulators.length})</span>
          )}
        </TabsTrigger>
        <TabsTrigger value="btts">
          BTTS / O2.5
          {confidentGoals.length > 0 && (
            <span className="ml-1 text-xs text-muted-foreground">({confidentGoals.length})</span>
          )}
        </TabsTrigger>
        <TabsTrigger value="resultater">
          Resultater
          {results.length > 0 && (
            <span className="ml-1 text-xs text-muted-foreground">({results.length})</span>
          )}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="value-bets">
        <PredictionsCard predictions={predictions} loading={predictionsLoading} />
      </TabsContent>
      <TabsContent value="kombispill">
        <SafePicksCard safePicks={safePicks} accumulators={accumulators} loading={predictionsLoading} />
      </TabsContent>
      <TabsContent value="btts">
        <ConfidentGoalsCard confidentGoals={confidentGoals} loading={predictionsLoading} />
      </TabsContent>
      <TabsContent value="resultater">
        <ResultsCard results={results} loading={resultsLoading} />
      </TabsContent>
    </Tabs>
  )
}
