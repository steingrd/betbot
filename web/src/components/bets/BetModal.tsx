import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import type { Accumulator, BetInput, Prediction } from '@/types'

interface BetModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onPlace: (bet: BetInput) => Promise<unknown>
  prediction?: Prediction | null
  accumulator?: Accumulator | null
}

const QUICK_AMOUNTS = [10, 25, 50, 100]

function getMarketOdds(p: Prediction): number {
  const m = p.market.toLowerCase()
  if (m === 'home' || m === 'h') return p.odds_home ?? 0
  if (m === 'draw' || m === 'd') return p.odds_draw ?? 0
  if (m === 'away' || m === 'a') return p.odds_away ?? 0
  return p.odds_home ?? 0
}

export function BetModal({ open, onOpenChange, onPlace, prediction, accumulator }: BetModalProps) {
  const [odds, setOdds] = useState('')
  const [amount, setAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Reset when modal opens with new data
  useEffect(() => {
    if (open) {
      if (prediction) {
        setOdds(getMarketOdds(prediction).toFixed(2))
      } else if (accumulator) {
        setOdds(accumulator.combined_odds.toFixed(2))
      }
      setAmount('')
    }
  }, [open, prediction, accumulator])

  const oddsNum = parseFloat(odds) || 0
  const amountNum = parseFloat(amount) || 0
  const potentialWin = oddsNum * amountNum

  const handlePlace = async () => {
    if (amountNum <= 0 || oddsNum <= 0) return
    setSubmitting(true)
    try {
      if (prediction) {
        await onPlace({
          match_id: `${prediction.home_team}_vs_${prediction.away_team}`,
          bet_type: 'single',
          market: prediction.market,
          home_team: prediction.home_team,
          away_team: prediction.away_team,
          kickoff: prediction.kickoff,
          league: prediction.league,
          odds: oddsNum,
          amount: amountNum,
          model_prob: prediction.model_prob,
          edge: prediction.edge,
          consensus_count: prediction.consensus_count,
        })
      } else if (accumulator) {
        await onPlace({
          bet_type: 'accumulator',
          odds: oddsNum,
          amount: amountNum,
          model_prob: accumulator.avg_prob,
          consensus_count: accumulator.size,
          legs: accumulator.picks.map((p) => ({
            match_id: `${p.home_team}_vs_${p.away_team}`,
            market: p.predicted_outcome,
            home_team: p.home_team,
            away_team: p.away_team,
            kickoff: p.kickoff,
            odds: p.odds,
          })),
        })
      }
      onOpenChange(false)
    } catch {
      // TODO: show error
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base">
            {prediction ? 'Plasser spill' : 'Plasser kombispill'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Match info */}
          {prediction && (
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {prediction.home_team} vs {prediction.away_team}
              </p>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">{prediction.market}</Badge>
                <span className="text-xs text-muted-foreground">{prediction.league}</span>
                <span className="text-xs text-muted-foreground">{prediction.kickoff}</span>
              </div>
            </div>
          )}

          {accumulator && (
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Kombispill ({accumulator.size} kamper)</p>
              <div className="space-y-1 text-xs">
                {accumulator.picks.map((p, i) => (
                  <div key={i} className="flex justify-between text-muted-foreground">
                    <span>{p.home_team} vs {p.away_team}</span>
                    <span className="font-medium text-foreground">{p.predicted_outcome}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Odds input */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Odds</label>
            <Input
              type="number"
              step="0.01"
              min="1"
              value={odds}
              onChange={(e) => setOdds(e.target.value)}
              className="mt-1 font-mono"
            />
          </div>

          {/* Amount with quick-select */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Innsats (kr)</label>
            <div className="flex gap-2 mt-1">
              {QUICK_AMOUNTS.map((q) => (
                <Button
                  key={q}
                  type="button"
                  variant={amount === String(q) ? 'default' : 'outline'}
                  size="sm"
                  className="flex-1"
                  onClick={() => setAmount(String(q))}
                >
                  {q}
                </Button>
              ))}
            </div>
            <Input
              type="number"
              min="1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Annet belop..."
              className="mt-2 font-mono"
            />
          </div>

          {/* Potential win */}
          {amountNum > 0 && oddsNum > 0 && (
            <div className="rounded-md bg-muted/50 px-3 py-2 flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Mulig gevinst</span>
              <span className="text-lg font-bold font-mono">
                {potentialWin.toFixed(0)} kr
              </span>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Avbryt
          </Button>
          <Button
            onClick={handlePlace}
            disabled={amountNum <= 0 || oddsNum <= 0 || submitting}
          >
            {submitting ? 'Plasserer...' : 'Plasser spill'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
