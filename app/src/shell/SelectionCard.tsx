import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useArea, useLayer } from '@/api/hooks'
import { Stat } from '@/components/Stat'
import { Button } from '@/components/ui/button'
import { formatShadeTime } from '@/lib/format'
import { PRIORITY_META, WAIT_POINT_LABEL, driverLabel } from '@/lib/meta'
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
  const areaId = useUiStore((s) => s.areaId)
  const { data: area } = useArea(areaId)
  const blocks = useLayer(areaId, 'blocks', selection.kind === 'block')
  const segments = useLayer(areaId, 'segments', selection.kind === 'segment')
  const waitPoints = useLayer(areaId, 'waitPoints', selection.kind === 'waitPoint')

  if (selection.kind === 'block') {
    const p = blocks.data?.features.find((f) => f.properties.id === selection.id)?.properties
    if (!p) return null
    return (
      <div className="space-y-3">
        <div>
          <h3 className="font-semibold">Block {p.id.slice(2)}</h3>
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

  if (selection.kind === 'segment') {
    const p = segments.data?.features.find((f) => f.properties.id === selection.id)?.properties
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
      </div>
    )
  }

  const p = waitPoints.data?.features.find((f) => f.properties.id === selection.id)?.properties
  if (!p) return null
  const type = WAIT_POINT_LABEL[p.type] ?? p.type
  return (
    <div className="space-y-1">
      <h3 className="font-semibold">{p.name ?? type}</h3>
      <p className="text-sm text-muted-foreground">{type} · counts ×{p.weight} when ranking nearby blocks</p>
    </div>
  )
}
