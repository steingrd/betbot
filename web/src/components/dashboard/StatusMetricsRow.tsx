import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { TrendingUp } from 'lucide-react'
import type { DataStatus } from '@/types'

interface Props {
  status: DataStatus | null
  loading: boolean
}

function MetricCard({
  label,
  value,
  badge,
  footer,
  description,
  loading,
  tooltip,
}: {
  label: string
  value: string
  badge?: string
  footer?: string
  description?: string
  loading: boolean
  tooltip?: React.ReactNode
}) {
  const card = (
    <Card>
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {label}
          </CardTitle>
          {badge && (
            <Badge variant="secondary" className="text-xs gap-1 font-normal">
              <TrendingUp className="h-3 w-3" />
              {badge}
            </Badge>
          )}
        </div>
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
        description="Totalt antall kamper i databasen"
        loading={loading}
      />
      <MetricCard
        label="Ligaer"
        value={fmt(status?.league_count ?? null)}
        description="Aktive ligaer med data"
        loading={loading}
      />
      <MetricCard
        label="Modell"
        value={status?.model_version ?? '-'}
        description="Trent XGBoost-modell"
        loading={loading}
      />
      <MetricCard
        label="Presisjon (1X2)"
        value={pct(status?.acc_1x2 ?? null)}
        badge={status?.acc_1x2 != null ? pct(status.acc_1x2) : undefined}
        footer={status?.acc_over25 != null ? `Over 2.5: ${pct(status.acc_over25)}` : undefined}
        description={status?.acc_btts != null ? `BTTS: ${pct(status.acc_btts)}` : 'Modellpresisjon'}
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
