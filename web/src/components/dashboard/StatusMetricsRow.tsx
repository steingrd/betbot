import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { DataStatus } from '@/types'

interface Props {
  status: DataStatus | null
  loading: boolean
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

export function StatusMetricsRow({ status, loading }: Props) {
  const fmt = (n: number | null) => (n != null ? n.toLocaleString('nb-NO') : '-')
  const pct = (n: number | null) => (n != null ? `${(n * 100).toFixed(1)}%` : '-')

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
    </div>
  )
}
