import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
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
import { Target } from 'lucide-react'
import type { ConfidentGoalPick } from '@/types'
import { translateMarket } from '@/lib/utils'

interface Props {
  confidentGoals: ConfidentGoalPick[]
  loading: boolean
}

function probColor(prob: number): string {
  if (prob >= 0.70) return 'text-green-600 dark:text-green-400'
  if (prob >= 0.60) return 'text-yellow-600 dark:text-yellow-400'
  return ''
}

export function ConfidentGoalsCard({ confidentGoals, loading }: Props) {
  return (
    <Card className="flex flex-col min-h-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Sikre BTTS / Over 2.5</span>
          {confidentGoals.length > 0 && (
            <span className="text-xs font-normal text-muted-foreground">
              {confidentGoals.length} funnet
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        {loading ? (
          <div className="px-4 pb-4 space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : confidentGoals.length === 0 ? (
          <div className="px-4 pb-6 pt-4 text-center">
            <Target className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">
              Ingen sikre malpicks enna
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
                      <TableHead>Tid</TableHead>
                      <TableHead>Kamp</TableHead>
                      <TableHead>Liga</TableHead>
                      <TableHead>Marked</TableHead>
                      <TableHead className="text-right">Modell</TableHead>
                      <TableHead className="text-center">Enighet</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {confidentGoals.map((p, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-mono whitespace-nowrap">{p.kickoff}</TableCell>
                        <TableCell className="whitespace-nowrap">
                          {p.home_team} vs {p.away_team}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{p.league}</TableCell>
                        <TableCell className="font-medium">{translateMarket(p.market)}</TableCell>
                        <TableCell className={`text-right font-medium ${probColor(p.avg_prob)}`}>
                          {(p.avg_prob * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell className="text-center">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span>
                                <Badge
                                  variant={p.consensus_count === p.total_strategies ? 'default' : 'secondary'}
                                  className="cursor-default"
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
          </div>
        )}
      </CardContent>
    </Card>
  )
}
