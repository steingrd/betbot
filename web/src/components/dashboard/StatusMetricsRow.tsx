import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { BetSummary, DataStatus } from '@/types'

interface Props {
  status: DataStatus | null
  loading: boolean
  betSummary?: BetSummary | null
  betLoading?: boolean
}

function MetricCard({
  label,
  value,
  footer,
  description,
  children,
  loading,
  tooltip,
}: {
  label: string
  value?: string
  footer?: string
  description?: string
  children?: React.ReactNode
  loading: boolean
  tooltip?: React.ReactNode
}) {
  const card = (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-0">
        {loading ? (
          <Skeleton className="h-8 w-24 my-1" />
        ) : children ? (
          children
        ) : (
          <p className="text-3xl font-bold tracking-tight">{value}</p>
        )}
      </CardContent>
      <CardFooter className="flex-col items-start gap-0.5 pt-2">
        {footer && (
          <p className="text-sm font-medium flex items-center gap-1">
            {footer}
          </p>
        )}
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardFooter>
    </Card>
  )

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{card}</TooltipTrigger>
        <TooltipContent side="bottom">{tooltip}</TooltipContent>
      </Tooltip>
    )
  }

  return card
}

export function StatusMetricsRow({ status, loading, betSummary, betLoading = false }: Props) {
  const fmt = (n: number | null) => (n != null ? n.toLocaleString('nb-NO') : '-')
  const pct = (n: number | null) => (n != null ? `${(n * 100).toFixed(1)}%` : '-')
  const kr = (n: number | null | undefined) => (n != null ? `${n.toLocaleString('nb-NO', { maximumFractionDigits: 0 })} kr` : '-')

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        label="Kamper"
        value={fmt(status?.total_matches ?? null)}
        footer={status?.latest_date ? `Sist oppdatert ${status.latest_date}` : undefined}
        description={status?.league_count ? `${fmt(status.league_count)} ligaer` : 'Totalt antall kamper'}
        loading={loading}
      />
      <MetricCard
        label="Modell"
        description={status?.model_version ?? 'Trent modell'}
        loading={loading}
      >
        {status?.acc_1x2 != null ? (
          <div className="flex gap-4 py-1">
            <div>
              <p className="text-3xl font-bold tracking-tight">{pct(status.acc_1x2)}</p>
              <p className="text-xs text-muted-foreground">1X2</p>
            </div>
            <div>
              <p className="text-3xl font-bold tracking-tight">{pct(status.acc_over25 ?? null)}</p>
              <p className="text-xs text-muted-foreground">O2.5</p>
            </div>
            <div>
              <p className="text-3xl font-bold tracking-tight">{pct(status.acc_btts ?? null)}</p>
              <p className="text-xs text-muted-foreground">BTTS</p>
            </div>
          </div>
        ) : (
          <p className="text-3xl font-bold tracking-tight">-</p>
        )}
      </MetricCard>
      <MetricCard
        label="Aktive spill"
        value={betSummary ? String(betSummary.active_count) : '-'}
        footer={betSummary?.active_amount ? kr(betSummary.active_amount) + ' i spill' : undefined}
        description={betSummary ? [
          betSummary.max_potential_payout > 0 ? `Maks gevinst: ${kr(betSummary.max_potential_payout)}` : null,
          betSummary.latest_kickoff ? `Siste kamp: ${new Date(betSummary.latest_kickoff).toISOString().slice(0, 10)}` : null,
        ].filter(Boolean).join(' · ') || `${betSummary.win_count + betSummary.loss_count} avgjorte totalt` : 'Plasserte spill'}
        loading={betLoading}
      />
      <MetricCard
        label="Totalregnskap"
        value={betSummary ? kr(betSummary.net_profit) : '-'}
        footer={betSummary ? `ROI: ${betSummary.roi_pct.toFixed(1)}%` : undefined}
        description={betSummary ? `${betSummary.win_count}V / ${betSummary.loss_count}T` : 'Netto gevinst/tap'}
        loading={betLoading}
      />
    </div>
  )
}
