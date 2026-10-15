import { cssVar } from '@/lib/colors'
import { cn } from '@/lib/utils'
import { useScenarioStore } from '@/state/scenarioStore'
import { useUiStore } from '@/state/uiStore'
import { layersFor, legendOf, type LegendEntry } from './layerRegistry'

/** Entries for visible layers only, generated from the registry (UI_RULES.md §2). */
export function Legend() {
  const mode = useUiStore((s) => s.mode)
  const visible = useUiStore((s) => s.visibleLayers)
  const hasScenario = useScenarioStore((s) => s.view === 'scenario' && s.scenario[mode].changes.length > 0)
  const shown = layersFor(mode).filter((l) => visible[l.id as keyof typeof visible] && (!l.scenarioOnly || hasScenario))
  if (!shown.length) return null
  return (
    <details open className="group max-h-[60vh] max-w-56 overflow-y-auto rounded-lg border bg-background/95 p-3 text-xs shadow-sm" aria-label="Map legend">
      <summary className="cursor-pointer font-semibold text-muted-foreground group-open:mb-2">Legend</summary>
      <ul className="space-y-2">
        {shown.map((layer) => (
          <li key={layer.id}>
            <p className="mb-1 font-semibold">{layer.label}</p>
            <ul className="space-y-1">
              {legendOf(layer, mode).map((entry) => (
                <li key={entry.label} className="flex items-center gap-2 text-muted-foreground">
                  <Swatch entry={entry} />
                  {entry.label}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </details>
  )
}

function Swatch({ entry }: { entry: LegendEntry }) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-block shrink-0',
        entry.shape === 'fill' && 'size-3 rounded-[3px]',
        entry.shape === 'line' && 'h-1 w-4 rounded-full',
        entry.shape === 'dot' && 'size-2.5 rounded-full ring-2 ring-background',
      )}
      style={{ background: cssVar(entry.color) }}
    />
  )
}
