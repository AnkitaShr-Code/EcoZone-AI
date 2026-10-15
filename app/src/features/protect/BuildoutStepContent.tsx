import { useArea } from '@/api/hooks'
import type { ParcelProps } from '@/api/types'
import { Provenance } from '@/components/Provenance'
import { ScoreChanges } from '@/components/ScoreChanges'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatCount, formatDesign } from '@/lib/format'
import { useScenario } from '@/state/useScenario'
import { BUILDOUT_RADII_M, useProtectStore } from './protectStore'

/** Step 4 (optional): the chosen envelope on every vacant parcel nearby, rescored as one area. */
export function BuildoutStepContent({ parcelsInRadius }: { parcelsInRadius: ParcelProps[] }) {
  const { areaId, result } = useScenario()
  const { data: area } = useArea(areaId)
  const { design, buildout, setBuildout } = useProtectStore()
  if (!design) return null
  const risks = result?.parcelRisk ? Object.values(result.parcelRisk) : []
  const high = risks.filter((r) => r.label === 'HIGH').length

  return (
    <div className="space-y-4">
      <div className="space-y-1 rounded-lg border p-3 text-sm">
        <p className="flex items-center justify-between font-semibold">Envelope <Provenance kind="planner" /></p>
        <p className="text-muted-foreground">{formatDesign(design)}</p>
        <p className="text-xs text-muted-foreground">The maximum the rules would allow on each parcel. Change it in step 2.</p>
      </div>

      <div className="space-y-1.5">
        <p className="text-sm font-semibold">Parcels within</p>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          spacing={0}
          value={String(buildout.radiusM)}
          onValueChange={(v) => v && setBuildout({ radiusM: Number(v), ran: false })}
          aria-label="Build-out radius"
        >
          {BUILDOUT_RADII_M.map((r) => <ToggleGroupItem key={r} value={String(r)} className="px-3">{r} m</ToggleGroupItem>)}
        </ToggleGroup>
        <p className="text-xs text-muted-foreground">{formatCount(parcelsInRadius.length, 'vacant parcel')} including this one.</p>
      </div>

      {buildout.ran && (
        <section className="space-y-2" aria-live="polite">
          <h3 className="text-sm font-semibold">Whole area, today and built out</h3>
          {result && area ? (
            <>
              <ScoreChanges before={result.before} after={result.after} indices={['acs', 'vci', 'hei', 'pss']} />
              <p className="text-sm">{formatCount(high, 'parcel')} at high risk of {parcelsInRadius.length}; {formatCount(result.blocksWorse, 'existing block')} lose cooling score.</p>
            </>
          ) : (
            <Skeleton className="h-32 w-full" />
          )}
        </section>
      )}
    </div>
  )
}
