import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useArea, useLayer, useSites } from '@/api/hooks'
import { Stat } from '@/components/Stat'
import { Button } from '@/components/ui/button'
import { formatBlock, formatInr, formatShadeTime } from '@/lib/format'
import { INTERVENTION_META, PRIORITY_META, TIME_TO_BENEFIT_LABEL, WAIT_POINT_LABEL, driverLabel } from '@/lib/meta'
import { useCostsStore } from '@/state/costsStore'
import { useScenarioStore } from '@/state/scenarioStore'
import { useUiStore, type Selection } from '@/state/uiStore'

/** Details of what the user clicked on the map (UI_RULES.md §1, principle 2). */
export function SelectionCard() {
  const selection = useUiStore((s) => s.selection)
  const select = useUiStore((s) => s.select)
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    if (selection) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selection])
  if (!selection) return null
  return (
    <section ref={ref} className="scroll-mt-3 rounded-xl border border-map-selection/40 bg-card p-4" aria-label="Selected on map">
      <div className="mb-3 flex items-start justify-between gap-2">
        <p className="text-xs font-semibold text-muted-foreground">Selected on map</p>
        <Button variant="ghost" size="icon-xs" onClick={() => select(null)} aria-label="Clear selection">
          <X />
        </Button>
      </div>
      <SelectionBody selection={selection} />
    </section>
  )
}

function SelectionBody({ selection }: { selection: Selection }) {
  switch (selection.kind) {
    case 'block': return <BlockDetails id={selection.id} />
    case 'segment': return <SegmentDetails id={selection.id} />
    case 'waitPoint': return <WaitPointDetails id={selection.id} />
    case 'parcel': return <ParcelDetails id={selection.id} />
    case 'site': return <SiteDetails id={selection.id} />
  }
}

function useAreaId() {
  return useUiStore((s) => s.areaId)
}

function BlockDetails({ id }: { id: string }) {
  const { data } = useLayer(useAreaId(), 'blocks')
  const p = data?.features.find((f) => f.properties.id === id)?.properties
  if (!p) return null
  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-semibold">{formatBlock(p.id)}</h3>
        <p className="text-sm text-muted-foreground">{PRIORITY_META[p.priorityClass].label}{p.builtForm === 'dense_low_rise' ? ' · Dense low-rise housing' : ''}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stat index="pss" value={p.scores.pss} />
        <Stat index="hei" value={p.scores.hei} />
        <Stat index="gcs" value={p.scores.gcs} />
        <Stat index="vci" value={p.scores.vci} />
      </div>
      {p.drivers.length > 0 && <p className="text-xs text-muted-foreground">Why: {p.drivers.map(driverLabel).join(' · ')}</p>}
    </div>
  )
}

function SegmentDetails({ id }: { id: string }) {
  const areaId = useAreaId()
  const { data: area } = useArea(areaId)
  const { data } = useLayer(areaId, 'segments')
  const p = data?.features.find((f) => f.properties.id === id)?.properties
  if (!p || !area) return null
  return (
    <div className="space-y-2">
      <h3 className="font-semibold">{p.road ?? `Unnamed ${p.roadClass} road`}</h3>
      <p className="text-sm text-muted-foreground">Footpath section, {Math.round(p.lengthM)} m{p.nearWait ? ' · near a waiting point' : ''}</p>
      <ul className="flex gap-2 text-sm">
        {area.shadeTimes.map((t, i) => (
          <li key={t} className="flex-1 rounded-lg bg-muted/60 px-2 py-1.5 text-center">
            <span className="block text-xs text-muted-foreground">{formatShadeTime(t)}</span>
            {p.shaded[i] ? 'Shade' : 'Sun'}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">Today's shade. Switch the map to the plan to see the change.</p>
    </div>
  )
}

function WaitPointDetails({ id }: { id: string }) {
  const { data } = useLayer(useAreaId(), 'waitPoints')
  const p = data?.features.find((f) => f.properties.id === id)?.properties
  if (!p) return null
  const type = WAIT_POINT_LABEL[p.type] ?? p.type
  return (
    <div className="space-y-1">
      <h3 className="font-semibold">{p.name ?? type}</h3>
      <p className="text-sm text-muted-foreground">{type} · counts ×{p.weight} when ranking nearby blocks</p>
    </div>
  )
}

function ParcelDetails({ id }: { id: string }) {
  const { data } = useLayer(useAreaId(), 'parcels')
  const p = data?.features.find((f) => f.properties.id === id)?.properties
  if (!p) return null
  return (
    <div className="space-y-1">
      <h3 className="font-semibold">{p.name}</h3>
      <p className="text-sm text-muted-foreground">{p.areaM2.toLocaleString('en-IN')} m² plot · street {p.roadWidthM} m wide · neighbours about {Math.round(p.neighbourHeightM / 3)} floors</p>
    </div>
  )
}

function SiteDetails({ id }: { id: string }) {
  const { data: sites } = useSites(useAreaId())
  const unitCosts = useCostsStore((s) => s.unitCosts)
  const inPlan = useScenarioStore((s) => s.scenario.repair.changes.some((c) => c.siteId === id))
  const site = sites?.find((s) => s.id === id)
  if (!site) return null
  const meta = INTERVENTION_META[site.type]
  return (
    <div className="space-y-1.5">
      <h3 className="font-semibold">{site.name}</h3>
      <p className="text-sm text-muted-foreground">
        {meta.label} · {inPlan ? 'In the plan' : 'Not in the plan'}
        {unitCosts && ` · ${formatInr(site.quantity * unitCosts[site.type].inr)}`} · {TIME_TO_BENEFIT_LABEL[site.timeToBenefit]} to benefit
      </p>
      {site.singleSite.ventilation.ok
        ? <p className="text-xs text-muted-foreground">Why: {site.singleSite.drivers.map(driverLabel).join(' · ')}</p>
        : <p className="text-xs text-status-rejected">Rejected: {site.singleSite.ventilation.reason}</p>}
    </div>
  )
}
