import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ChevronDown, Trash2, Plus } from 'lucide-react'
import type { ModelInfo } from '@/types'
import { CreateModelDialog } from './CreateModelDialog'

interface Props {
  models: ModelInfo[]
  activeSlug: string
  onSelect: (slug: string) => void
  onCreate: (data: { name: string; strategies: string[]; years?: number | null }) => Promise<ModelInfo>
  onDelete: (slug: string) => void
}

export function ModelSelector({ models, activeSlug, onSelect, onCreate, onDelete }: Props) {
  const [open, setOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  const activeModel = models.find(m => m.slug === activeSlug)
  const label = activeModel?.name ?? activeSlug

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="gap-1"
      >
        {label}
        <ChevronDown className="h-3 w-3" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Velg modell</DialogTitle>
          </DialogHeader>
          <div className="space-y-1">
            {models.map(m => (
              <div
                key={m.slug}
                className={`flex items-center justify-between p-2 rounded cursor-pointer hover:bg-muted ${
                  m.slug === activeSlug ? 'bg-muted' : ''
                }`}
                onClick={() => { onSelect(m.slug); setOpen(false) }}
              >
                <div>
                  <span className="text-sm font-medium">{m.name}</span>
                  <div className="flex gap-1 mt-0.5">
                    {m.strategies.map(s => (
                      <Badge key={s} variant="secondary" className="text-xs px-1 py-0">
                        {s}
                      </Badge>
                    ))}
                    {m.years && (
                      <Badge variant="outline" className="text-xs px-1 py-0">
                        {m.years} ar
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {!m.is_trained && (
                    <Badge variant="destructive" className="text-xs px-1 py-0">
                      utrent
                    </Badge>
                  )}
                  {m.slug !== 'standard' && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete(m.slug)
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-2"
            onClick={() => { setOpen(false); setCreateOpen(true) }}
          >
            <Plus className="h-4 w-4 mr-1" />
            Ny modell
          </Button>
        </DialogContent>
      </Dialog>

      <CreateModelDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={onCreate}
      />
    </>
  )
}
