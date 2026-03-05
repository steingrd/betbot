import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Layers } from 'lucide-react'
import type { Accumulator, PlacedBetRef, SafePick } from '@/types'
import { translateMarket } from '@/lib/utils'

interface Props {
  safePicks: SafePick[]
  accumulators: Accumulator[]
  loading: boolean
  placedIds?: PlacedBetRef[]
  onAccumulatorClick?: (accumulator: Accumulator) => void
}

export function SafePicksCard({ safePicks, accumulators, loading, placedIds: _placedIds, onAccumulatorClick }: Props) {
  const availableSizes = accumulators.map((a) => String(a.size))
  const [selectedSize, setSelectedSize] = useState<string>(availableSizes[0] || '4')

  const selectedAccumulator = accumulators.find((a) => String(a.size) === selectedSize)

  return (
    <Card className="flex flex-col min-h-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Sikre kombispill</span>
          <div className="flex items-center gap-3">
            {availableSizes.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-normal text-muted-foreground">Kamper:</span>
                <ToggleGroup
                  type="single"
                  value={selectedSize}
                  onValueChange={(v) => v && setSelectedSize(v)}
                  size="sm"
                  className="gap-0.5"
                >
                  {availableSizes.map((n) => (
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
            {selectedAccumulator && (
              <Badge variant="secondary" className="text-xs font-mono">
                Odds: {selectedAccumulator.combined_odds.toFixed(1)}
              </Badge>
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
        ) : safePicks.length === 0 ? (
          <div className="px-4 pb-6 pt-4 text-center">
            <Layers className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">
              Ingen sikre picks enna
            </p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              Klikk "Finn value bets" for a analysere dagens kamper
            </p>
          </div>
        ) : (
          <div className="px-4 pb-4">
            <TooltipProvider>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Tid</TableHead>
                      <TableHead className="text-xs">Kamp</TableHead>
                      <TableHead className="text-xs">Liga</TableHead>
                      <TableHead className="text-xs">Utfall</TableHead>
                      <TableHead className="text-xs text-right">Odds</TableHead>
                      <TableHead className="text-xs text-right">Modell</TableHead>
                      <TableHead className="text-xs text-center">Enighet</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(selectedAccumulator?.picks || safePicks).map((p, i) => (
                      <TableRow key={i} className={selectedAccumulator && i < selectedAccumulator.size ? '' : 'opacity-50'}>
                        <TableCell className="font-mono text-xs whitespace-nowrap">{p.kickoff}</TableCell>
                        <TableCell className="text-xs whitespace-nowrap">
                          {p.home_team} vs {p.away_team}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{p.league}</TableCell>
                        <TableCell className="text-xs font-medium">{translateMarket(p.predicted_outcome)}</TableCell>
                        <TableCell className="text-right text-xs font-mono text-muted-foreground">
                          {p.odds != null ? p.odds.toFixed(2) : '-'}
                        </TableCell>
                        <TableCell className="text-right text-xs">
                          <span className={p.avg_prob >= 0.7 ? 'text-green-600 dark:text-green-400' : ''}>
                            {(p.avg_prob * 100).toFixed(1)}%
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span>
                                <Badge
                                  variant={p.consensus_count === p.total_strategies ? 'default' : 'secondary'}
                                  className="text-xs cursor-default"
                                >
                                  {p.consensus_count}/{p.total_strategies}
                                </Badge>
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="left" className="text-xs">
                              {Object.entries(p.strategy_probs).map(([name, prob]) => (
                                <div key={name} className="flex justify-between gap-3">
                                  <span>{name}</span>
                                  <span className="font-mono">{(prob * 100).toFixed(1)}%</span>
                                </div>
                              ))}
                            </TooltipContent>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </TooltipProvider>
            {selectedAccumulator && (
              <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground border-t pt-2">
                <span>Kombinert odds:</span>
                <span className="font-mono font-medium text-foreground">
                  {selectedAccumulator.combined_odds.toFixed(2)}
                </span>
                <span className="mx-1">|</span>
                <span>Laveste prob:</span>
                <span className="font-mono font-medium text-foreground">
                  {(selectedAccumulator.min_prob * 100).toFixed(1)}%
                </span>
                <span className="mx-1">|</span>
                <span>Snitt prob:</span>
                <span className="font-mono font-medium text-foreground">
                  {(selectedAccumulator.avg_prob * 100).toFixed(1)}%
                </span>
                {onAccumulatorClick && (
                  <>
                    <span className="mx-1">|</span>
                    <button
                      onClick={() => onAccumulatorClick(selectedAccumulator)}
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      Plasser spill
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
