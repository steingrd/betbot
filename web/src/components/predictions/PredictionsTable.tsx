import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { PlacedBetRef, Prediction } from '@/types'
import { translateMarket } from '@/lib/utils'

interface Props {
  predictions: Prediction[]
  placedIds?: PlacedBetRef[]
  onRowClick?: (prediction: Prediction) => void
}

function isPlaced(p: Prediction, placedIds: PlacedBetRef[]): boolean {
  return placedIds.some(
    (ref) =>
      ref.bet_type === 'single' &&
      ref.market === p.market &&
      ref.match_id === `${p.home_team}_vs_${p.away_team}`
  )
}

function edgeColor(edge: number | null): string {
  if (edge == null) return ''
  const pct = edge * 100
  if (pct >= 10) return 'text-green-600 dark:text-green-400'
  if (pct >= 5) return 'text-yellow-600 dark:text-yellow-400'
  return ''
}

function fmtOdds(v: number | null): string {
  return v != null ? v.toFixed(2) : '-'
}

function consensusBadgeVariant(count: number | null, total: number | null): 'default' | 'secondary' | 'destructive' {
  if (count == null || total == null) return 'secondary'
  const ratio = count / total
  if (ratio >= 0.75) return 'default'
  if (ratio >= 0.5) return 'secondary'
  return 'destructive'
}

export function PredictionsTable({ predictions, placedIds = [], onRowClick }: Props) {
  return (
    <TooltipProvider>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Tid</TableHead>
              <TableHead className="text-xs">Kamp</TableHead>
              <TableHead className="text-xs">Liga</TableHead>
              <TableHead className="text-xs">Market</TableHead>
              <TableHead className="text-xs text-right">H</TableHead>
              <TableHead className="text-xs text-right">U</TableHead>
              <TableHead className="text-xs text-right">B</TableHead>
              <TableHead className="text-xs text-right">Modell</TableHead>
              <TableHead className="text-xs text-right">Edge</TableHead>
              <TableHead className="text-xs text-center">Enighet</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {predictions.map((p, i) => (
              <TableRow
                key={i}
                className={`${onRowClick ? 'cursor-pointer hover:bg-muted/50' : ''} ${isPlaced(p, placedIds) ? 'bg-green-500/10' : ''}`}
                onClick={() => onRowClick?.(p)}
              >
                <TableCell className="font-mono text-xs whitespace-nowrap">{p.kickoff}</TableCell>
                <TableCell className="text-xs whitespace-nowrap">
                  {p.home_team} vs {p.away_team}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{p.league}</TableCell>
                <TableCell className="text-xs font-medium">{translateMarket(p.market)}</TableCell>
                <TableCell className="text-right text-xs font-mono text-muted-foreground">
                  {fmtOdds(p.odds_home)}
                </TableCell>
                <TableCell className="text-right text-xs font-mono text-muted-foreground">
                  {fmtOdds(p.odds_draw)}
                </TableCell>
                <TableCell className="text-right text-xs font-mono text-muted-foreground">
                  {fmtOdds(p.odds_away)}
                </TableCell>
                <TableCell className="text-right text-xs">
                  {p.model_prob != null ? `${(p.model_prob * 100).toFixed(1)}%` : '-'}
                </TableCell>
                <TableCell className={`text-right text-xs font-medium ${edgeColor(p.edge)}`}>
                  {p.edge != null ? `${(p.edge * 100).toFixed(1)}%` : '-'}
                </TableCell>
                <TableCell className="text-center">
                  {p.consensus_count != null && p.total_strategies != null ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span>
                          <Badge
                            variant={consensusBadgeVariant(p.consensus_count, p.total_strategies)}
                            className="text-xs cursor-default"
                          >
                            {p.consensus_count}/{p.total_strategies}
                          </Badge>
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="text-xs">
                        {p.signals?.map((s, j) => (
                          <div key={j} className="flex justify-between gap-3">
                            <span>{s.is_value ? '\u2713' : '\u2717'} {s.strategy}</span>
                            <span className="font-mono">{(s.prob * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span className="text-xs text-muted-foreground">-</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  )
}
