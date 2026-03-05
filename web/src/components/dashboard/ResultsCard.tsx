import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { MatchResult } from '@/types'

interface Props {
  results: MatchResult[]
  loading: boolean
}

export function ResultsCard({ results, loading }: Props) {
  return (
    <Card className="flex flex-col min-h-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Siste resultater</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 p-0">
        {loading ? (
          <div className="px-4 pb-4 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : results.length === 0 ? (
          <p className="px-4 pb-4 text-sm text-muted-foreground">
            Ingen resultater tilgjengelig.
          </p>
        ) : (
          <div className="overflow-x-auto px-2 pb-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dato</TableHead>
                  <TableHead>Liga</TableHead>
                  <TableHead className="text-right">Hjemme</TableHead>
                  <TableHead className="text-center">Score</TableHead>
                  <TableHead>Borte</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono whitespace-nowrap">
                      {r.date}
                    </TableCell>
                    <TableCell className="text-muted-foreground truncate max-w-[100px]">
                      {r.league || '-'}
                    </TableCell>
                    <TableCell className="text-right truncate max-w-[120px]">
                      {r.home_team}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="secondary" className="font-mono px-1.5">
                        {r.home_goals}-{r.away_goals}
                      </Badge>
                    </TableCell>
                    <TableCell className="truncate max-w-[120px]">
                      {r.away_team}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
