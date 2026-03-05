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
  loading,
  tooltip,
}: {
  label: string
  value: string
  footer?: string
  description?: string
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
        value={status?.model_version ?? '-'}
        description={
          status?.acc_1x2 != null
            ? `1X2 ${pct(status.acc_1x2)} | O2.5 ${pct(status.acc_over25 ?? null)} | BTTS ${pct(status.acc_btts ?? null)}`
            : 'Trent modell'
        }
        loading={loading}
        tooltip={
          <div className="text-xs space-y-1">
            <p>1X2: {pct(status?.acc_1x2 ?? null)}</p>
            <p>Over 2.5: {pct(status?.acc_over25 ?? null)}</p>
            <p>BTTS: {pct(status?.acc_btts ?? null)}</p>
          </div>
        }
      />
      <MetricCard
        label="Aktive spill"
        value={betSummary ? String(betSummary.active_count) : '-'}
        footer={betSummary?.active_amount ? kr(betSummary.active_amount) + ' i spill' : undefined}
        description={betSummary ? [
          betSummary.max_potential_payout > 0 ? `Maks gevinst: ${kr(betSummary.max_potential_payout)}` : null,
          betSummary.latest_kickoff ? `Siste kamp: ${new Date(betSummary.latest_kickoff).toLocaleString('no-NO', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}` : null,
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
