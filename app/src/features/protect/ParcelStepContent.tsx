import { MousePointerClick } from 'lucide-react'
import { useLayer } from '@/api/hooks'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { flyTo } from '@/map/mapController'
import { useUiStore } from '@/state/uiStore'

/** Step 1: the candidate parcels as a list (the map's list equivalent). Selecting one highlights it. */
export function ParcelStepContent() {
  const areaId = useUiStore((s) => s.areaId)
  const selection = useUiStore((s) => s.selection)
  const select = useUiStore((s) => s.select)
  const { data: parcels } = useLayer(areaId, 'parcels')
  if (!parcels) return <Skeleton className="h-40 w-full" />

  return (
    <div className="space-y-3">
      {selection?.kind !== 'parcel' && (
        <EmptyState icon={MousePointerClick}>Click a vacant parcel on the map, or pick one from the list.</EmptyState>
      )}
      <ul className="divide-y rounded-lg border" aria-label="Vacant parcels">
        {parcels.features.map(({ properties: p }) => {
          const selected = selection?.kind === 'parcel' && selection.id === p.id
          return (
            <li key={p.id}>
              <button
                type="button"
                aria-pressed={selected}
                className={cn('w-full px-3 py-2 text-left hover:bg-muted/60', selected && 'bg-map-selection/10')}
                onClick={() => {
                  select({ kind: 'parcel', id: p.id })
                  flyTo(p.center, 17)
                }}
              >
                <span className="block text-sm">{p.name}</span>
                <span className="block text-xs text-muted-foreground">{p.areaM2.toLocaleString('en-IN')} m² · street {p.roadWidthM} m wide</span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
