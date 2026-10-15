import { useLayer } from '@/api/hooks'
import type { Explanation } from '@/api/types'
import { ExplanationCard } from '@/components/ExplanationCard'
import { Provenance } from '@/components/Provenance'
import { RiskBadge } from '@/components/RiskBadge'
import { ScoreChanges } from '@/components/ScoreChanges'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { useScenario } from '@/state/useScenario'
import { DesignSliders } from './DesignSliders'
import { useProtectStore } from './protectStore'

interface Props {
  explanation: Explanation | undefined
  explanationStale: boolean
}

/** Step 2: proposal sliders with the engine's before and after for the parcel's block. */
export function ProposalStepContent({ explanation, explanationStale }: Props) {
  const { areaId, result } = useScenario()
  const { parcelId, design, keepFloorAreaPct, setDesign, setKeepFloorAreaPct } = useProtectStore()
  const { data: parcels } = useLayer(areaId, 'parcels')
  const parcel = parcels?.features.find((f) => f.properties.id === parcelId)?.properties
  if (!design || !parcel) return null
  const block = result?.blocks.find((b) => b.id === parcel.blockId)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">{parcel.name}</p>
        <Provenance kind="planner" />
      </div>
      <DesignSliders design={design} onChange={setDesign} />

      <section className="space-y-2" aria-live="polite" aria-label="Impact on the parcel's block">
        <h3 className="text-sm font-semibold">Impact on the parcel's block</h3>
        {result?.risk && block ? (
          <>
            <RiskBadge risk={result.risk} />
            <ScoreChanges before={block.before} after={block.after} indices={['vci', 'hei', 'gcs', 'pss']} />
            {result.blocksWorse > 0 && <p className="text-xs text-muted-foreground">{result.blocksWorse} existing blocks around the parcel lose cooling score.</p>}
          </>
        ) : (
          <Skeleton className="h-32 w-full" />
        )}
      </section>

      {explanation && <ExplanationCard explanation={explanation} staleNote={explanationStale ? 'You have changed the proposal since this was written.' : undefined} />}

      <div className="space-y-2 rounded-lg border p-3">
        <div className="flex items-baseline justify-between">
          <Label htmlFor="keep-floor-area">Option B keeps at least</Label>
          <span className="text-sm tabular-nums">{keepFloorAreaPct}% of floor area</span>
        </div>
        <Slider id="keep-floor-area" min={50} max={95} step={5} value={[keepFloorAreaPct]} onValueChange={([v]) => setKeepFloorAreaPct(v)} aria-label="Floor area option B keeps" />
        <p className="text-xs text-muted-foreground">Used when searching for better designs. <Provenance kind="planner" className="py-0" /></p>
      </div>
    </div>
  )
}
