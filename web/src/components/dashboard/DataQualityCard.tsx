import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { DataStatus } from '@/types'

interface Props {
  status: DataStatus | null
  loading: boolean
}

function Metric({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={value && value !== '-' ? 'font-medium' : 'text-muted-foreground'}>
        {value || '-'}
      </span>
    </div>
  )
}

export function DataQualityCard({ status, loading }: Props) {
  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Datakvalitet</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Laster...</CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Datakvalitet</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5">
        <Metric label="Siste data" value={status?.latest_date} />
        <Metric label="Ligaer" value={status?.league_count?.toString()} />
        <Metric
          label="Kamper"
          value={status?.total_matches ? status.total_matches.toLocaleString('nb-NO') : null}
        />
        <Metric
          label="Modell"
          value={status?.model_version ? `v${status.model_version.slice(0, 8)}` : null}
        />
        <Metric
          label="1X2 acc"
          value={status?.acc_1x2 != null ? `${(status.acc_1x2 * 100).toFixed(1)}%` : null}
        />
        <Metric
          label="Over 2.5"
          value={status?.acc_over25 != null ? `${(status.acc_over25 * 100).toFixed(1)}%` : null}
        />
        <Metric
          label="BTTS"
          value={status?.acc_btts != null ? `${(status.acc_btts * 100).toFixed(1)}%` : null}
        />
      </CardContent>
    </Card>
  )
}
