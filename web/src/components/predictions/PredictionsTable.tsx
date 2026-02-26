import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { Prediction } from '@/types'

interface Props {
  predictions: Prediction[]
}

const confidenceVariant: Record<string, 'default' | 'secondary' | 'destructive'> = {
  High: 'default',
  Medium: 'secondary',
  Low: 'destructive',
}

export function PredictionsTable({ predictions }: Props) {
  if (predictions.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">Ingen value bets funnet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tid</TableHead>
            <TableHead>Kamp</TableHead>
            <TableHead>Liga</TableHead>
            <TableHead>Market</TableHead>
            <TableHead className="text-right">Modell</TableHead>
            <TableHead className="text-right">Edge</TableHead>
            <TableHead>Konf.</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {predictions.map((p, i) => (
            <TableRow key={i}>
              <TableCell className="font-mono text-xs">{p.kickoff}</TableCell>
              <TableCell className="text-xs">
                {p.home_team} vs {p.away_team}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">{p.league}</TableCell>
              <TableCell className="text-xs font-medium">{p.market}</TableCell>
              <TableCell className="text-right text-xs">
                {p.model_prob != null ? `${(p.model_prob * 100).toFixed(1)}%` : '-'}
              </TableCell>
              <TableCell className="text-right text-xs font-medium">
                {p.edge != null ? `${(p.edge * 100).toFixed(1)}%` : '-'}
              </TableCell>
              <TableCell>
                <Badge variant={confidenceVariant[p.confidence] || 'secondary'} className="text-xs">
                  {p.confidence}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
