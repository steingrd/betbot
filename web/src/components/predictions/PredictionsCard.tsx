import { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { PredictionsTable } from './PredictionsTable'
import { TrendingUp } from 'lucide-react'
import type { Prediction } from '@/types'

interface Props {
  predictions: Prediction[]
  loading: boolean
}

export function PredictionsCard({ predictions, loading }: Props) {
  const [minConsensus, setMinConsensus] = useState('2')

  const hasConsensusData = predictions.some((p) => p.consensus_count != null)

  const filtered = useMemo(() => {
    if (!hasConsensusData) return predictions
    const threshold = parseInt(minConsensus, 10)
    return predictions.filter(
      (p) => p.consensus_count != null && p.consensus_count >= threshold
    )
  }, [predictions, minConsensus, hasConsensusData])

  return (
    <Card className="flex flex-col min-h-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Value Bets</span>
          <div className="flex items-center gap-3">
            {hasConsensusData && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-normal text-muted-foreground">Enighet:</span>
                <ToggleGroup
                  type="single"
                  value={minConsensus}
                  onValueChange={(v) => v && setMinConsensus(v)}
                  size="sm"
                  className="gap-0.5"
                >
                  {['1', '2', '3', '4'].map((n) => (
                    <ToggleGroupItem
                      key={n}
                      value={n}
                      className="h-6 w-6 text-xs px-0"
                    >
                      {n}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </div>
            )}
            {filtered.length > 0 && (
              <span className="text-xs font-normal text-muted-foreground">
                {filtered.length} funnet
              </span>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        {loading ? (
          <div className="px-4 pb-4 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-4 pb-6 pt-4 text-center">
            <TrendingUp className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">
              {predictions.length > 0
                ? `Ingen bets med ${minConsensus}+ strategier enige`
                : 'Ingen value bets enna'}
            </p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              {predictions.length > 0
                ? 'Senk enighet-kravet for a se flere'
                : 'Klikk \u00ABFinn value bets\u00BB for a analysere dagens kamper'}
            </p>
          </div>
        ) : (
          <div className="px-4 pb-4">
            <PredictionsTable predictions={filtered} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
