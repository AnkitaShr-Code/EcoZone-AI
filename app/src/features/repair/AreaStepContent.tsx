import { MapPin } from 'lucide-react'
import { useArea, useHotspots } from '@/api/hooks'
import { Provenance } from '@/components/Provenance'
import { Stat } from '@/components/Stat'
import { Skeleton } from '@/components/ui/skeleton'
import { cssVar } from '@/lib/colors'
import { formatBlock, formatCount } from '@/lib/format'
import { PRIORITY_META, driverLabel } from '@/lib/meta'
import { flyTo } from '@/map/mapController'
import { useUiStore } from '@/state/uiStore'

/** Step 1: the area's baseline and its top hotspots. */
export function AreaStepContent() {
  const areaId = useUiStore((s) => s.areaId)
  const select = useUiStore((s) => s.select)
  const { data: area } = useArea(areaId)
  const { data: hotspots } = useHotspots(areaId)

  if (!area) return <Skeleton className="h-40 w-full" />
  const defaultHeights = area.dataGaps.buildingsByHeightSource.typology ?? 0

  return (
    <div className="space-y-4">
      <div>
        <p className="flex items-center gap-1.5 text-sm font-semibold">
          <MapPin className="size-4 text-muted-foreground" aria-hidden />
          {area.name}, {area.city}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatCount(area.counts.blocks, 'block')} · {formatCount(area.counts.buildings, 'building')} · {formatCount(area.counts.waitPoints, 'waiting point')}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Stat index="acs" value={area.baseline.acs} />
        <Stat index="pss" value={area.baseline.pss} />
        <Stat index="hei" value={area.baseline.hei} />
        <Stat index="gcs" value={area.baseline.gcs} />
      </div>

      {defaultHeights > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Provenance kind="default" />
          {defaultHeights} of {area.counts.buildings} buildings use a default height for their building type.
        </p>
      )}

      <div>
        <h3 className="mb-1.5 text-sm font-semibold">Top hotspots</h3>
        <ol className="divide-y rounded-lg border">
          {(hotspots ?? []).slice(0, 5).map((h) => (
            <li key={h.blockId}>
              <button
                type="button"
                className="flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-muted/60 focus-visible:bg-muted/60"
                onClick={() => {
                  select({ kind: 'block', id: h.blockId })
                  flyTo(h.centroid, 17)
                }}
              >
                <span className="mt-0.5 text-xs font-semibold text-muted-foreground tabular-nums">{h.rank}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-sm">
                    <span className="size-2.5 rounded-sm" style={{ background: cssVar(PRIORITY_META[h.priorityClass].color) }} aria-hidden />
                    {formatBlock(h.blockId)} · {PRIORITY_META[h.priorityClass].label}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">{h.drivers.map(driverLabel).join(' · ')}</span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
