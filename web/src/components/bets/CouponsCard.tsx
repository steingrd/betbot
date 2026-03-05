import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { ChevronDown, ChevronRight, Receipt, X } from 'lucide-react'
import type { BetRecord } from '@/types'
import { translateMarket } from '@/lib/utils'

interface Props {
  bets: BetRecord[]
  loading: boolean
  onCancel: (id: number) => void
}

function statusBadge(status: string) {
  switch (status) {
    case 'won':
      return <Badge className="bg-green-600 text-xs">Vunnet</Badge>
    case 'lost':
      return <Badge variant="destructive" className="text-xs">Tapt</Badge>
    case 'pending':
      return <Badge variant="secondary" className="text-xs">Aktiv</Badge>
    case 'cancelled':
      return <Badge variant="outline" className="text-xs text-muted-foreground">Kansellert</Badge>
    default:
      return <Badge variant="secondary" className="text-xs">{status}</Badge>
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`
  } catch {
    return iso
  }
}

function profitColor(profit: number | null): string {
  if (profit == null) return ''
  if (profit > 0) return 'text-green-600 dark:text-green-400'
  if (profit < 0) return 'text-red-600 dark:text-red-400'
  return ''
}

export function CouponsCard({ bets, loading, onCancel }: Props) {
  const [filter, setFilter] = useState('all')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const filtered = filter === 'all'
    ? bets.filter((b) => b.status !== 'cancelled')
    : bets.filter((b) => b.status === filter)

  return (
    <Card className="flex flex-col min-h-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Kuponger</span>
          <div className="flex items-center gap-3">
            <ToggleGroup
              type="single"
              value={filter}
              onValueChange={(v) => v && setFilter(v)}
              size="sm"
              className="gap-0.5"
            >
              <ToggleGroupItem value="all" className="h-6 text-xs px-2">Alle</ToggleGroupItem>
              <ToggleGroupItem value="pending" className="h-6 text-xs px-2">Aktive</ToggleGroupItem>
              <ToggleGroupItem value="won" className="h-6 text-xs px-2">Vunnet</ToggleGroupItem>
              <ToggleGroupItem value="lost" className="h-6 text-xs px-2">Tapt</ToggleGroupItem>
            </ToggleGroup>
            {filtered.length > 0 && (
              <span className="text-xs font-normal text-muted-foreground">
                {filtered.length} spill
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
            <Receipt className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm font-medium text-muted-foreground">
              Ingen kuponger enna
            </p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              Klikk pa en value bet for a plassere et spill
            </p>
          </div>
        ) : (
          <div className="px-4 pb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs w-6"></TableHead>
                    <TableHead className="text-xs">Dato</TableHead>
                    <TableHead className="text-xs">Kamp</TableHead>
                    <TableHead className="text-xs">Marked</TableHead>
                    <TableHead className="text-xs text-right">Odds</TableHead>
                    <TableHead className="text-xs text-right">Innsats</TableHead>
                    <TableHead className="text-xs text-center">Status</TableHead>
                    <TableHead className="text-xs text-right">Resultat</TableHead>
                    <TableHead className="text-xs w-8"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((bet) => (
                    <>
                      <TableRow
                        key={bet.id}
                        className={bet.bet_type === 'accumulator' ? 'cursor-pointer' : ''}
                        onClick={() => {
                          if (bet.bet_type === 'accumulator') {
                            setExpandedId(expandedId === bet.id ? null : bet.id)
                          }
                        }}
                      >
                        <TableCell className="text-xs px-1">
                          {bet.bet_type === 'accumulator' && (
                            expandedId === bet.id
                              ? <ChevronDown className="h-3 w-3" />
                              : <ChevronRight className="h-3 w-3" />
                          )}
                        </TableCell>
                        <TableCell className="text-xs font-mono whitespace-nowrap">
                          {formatDate(
                            bet.bet_type === 'accumulator' && bet.legs?.length
                              ? bet.legs.reduce((latest, leg) => leg.kickoff && leg.kickoff > latest ? leg.kickoff : latest, bet.legs[0].kickoff ?? bet.created_at)
                              : bet.kickoff ?? bet.created_at
                          )}
                        </TableCell>
                        <TableCell className="text-xs whitespace-nowrap">
                          {bet.bet_type === 'accumulator'
                            ? `Kombi (${bet.legs?.length ?? 0} kamper)`
                            : `${bet.home_team} vs ${bet.away_team}`}
                        </TableCell>
                        <TableCell className="text-xs font-medium">
                          {bet.bet_type === 'accumulator' ? '-' : translateMarket(bet.market)}
                        </TableCell>
                        <TableCell className="text-right text-xs font-mono">
                          {bet.odds.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right text-xs font-mono">
                          {bet.amount} kr
                        </TableCell>
                        <TableCell className="text-center">
                          {statusBadge(bet.status)}
                        </TableCell>
                        <TableCell className={`text-right text-xs font-mono font-medium ${profitColor(bet.profit)}`}>
                          {bet.profit != null
                            ? `${bet.profit >= 0 ? '+' : ''}${bet.profit.toFixed(0)} kr`
                            : '-'}
                        </TableCell>
                        <TableCell className="px-1">
                          {bet.status === 'pending' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={(e) => {
                                e.stopPropagation()
                                onCancel(bet.id)
                              }}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                      {/* Expanded accumulator legs */}
                      {bet.bet_type === 'accumulator' && expandedId === bet.id && bet.legs?.map((leg) => (
                        <TableRow key={`leg-${leg.id}`} className="bg-muted/30">
                          <TableCell></TableCell>
                          <TableCell className="text-xs text-muted-foreground">{leg.kickoff}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {leg.home_team} vs {leg.away_team}
                          </TableCell>
                          <TableCell className="text-xs">{translateMarket(leg.market)}</TableCell>
                          <TableCell className="text-right text-xs font-mono text-muted-foreground">
                            {leg.odds?.toFixed(2) ?? '-'}
                          </TableCell>
                          <TableCell></TableCell>
                          <TableCell className="text-center">
                            {statusBadge(leg.result)}
                          </TableCell>
                          <TableCell></TableCell>
                          <TableCell></TableCell>
                        </TableRow>
                      ))}
                    </>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
