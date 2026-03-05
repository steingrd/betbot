import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { ModelInfo } from '@/types'

const ALL_STRATEGIES = ['xgboost', 'poisson', 'elo', 'logreg'] as const
const YEAR_OPTIONS = [
  { label: 'Alle', value: null },
  { label: '10 ar', value: 10 },
  { label: '5 ar', value: 5 },
  { label: '3 ar', value: 3 },
]

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: { name: string; strategies: string[]; years?: number | null }) => Promise<ModelInfo>
}

export function CreateModelDialog({ open, onOpenChange, onCreate }: Props) {
  const [name, setName] = useState('')
  const [strategies, setStrategies] = useState<string[]>([...ALL_STRATEGIES])
  const [years, setYears] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggleStrategy = (slug: string) => {
    setStrategies(prev =>
      prev.includes(slug)
        ? prev.filter(s => s !== slug)
        : [...prev, slug]
    )
  }

  const handleCreate = async () => {
    if (!name.trim() || strategies.length === 0) return
    setCreating(true)
    setError(null)
    try {
      await onCreate({ name: name.trim(), strategies, years })
      setName('')
      setStrategies([...ALL_STRATEGIES])
      setYears(null)
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Feil ved opprettelse')
    } finally {
      setCreating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Ny modell</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Navn</label>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="F.eks. Siste 5 ar"
              className="mt-1"
            />
          </div>

          <div>
            <label className="text-sm font-medium">Strategier</label>
            <div className="flex gap-2 mt-1">
              {ALL_STRATEGIES.map(s => (
                <Button
                  key={s}
                  variant={strategies.includes(s) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => toggleStrategy(s)}
                  className="text-xs"
                >
                  {s}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">Tidsperiode</label>
            <div className="flex gap-2 mt-1">
              {YEAR_OPTIONS.map(opt => (
                <Button
                  key={opt.label}
                  variant={years === opt.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setYears(opt.value)}
                  className="text-xs"
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <Button
            onClick={handleCreate}
            disabled={!name.trim() || strategies.length === 0 || creating}
            className="w-full"
          >
            {creating ? 'Oppretter...' : 'Opprett modell'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
