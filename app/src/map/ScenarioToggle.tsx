import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useScenarioStore, type MapView } from '@/state/scenarioStore'
import { useUiStore } from '@/state/uiStore'

const SCENARIO_LABEL = { repair: 'With plan', protect: 'With proposal' } as const

/** Today vs the working scenario on the map; shown only once a scenario exists. */
export function ScenarioToggle() {
  const mode = useUiStore((s) => s.mode)
  const hasChanges = useScenarioStore((s) => s.scenario[mode].changes.length > 0)
  const view = useScenarioStore((s) => s.view)
  const setView = useScenarioStore((s) => s.setView)
  if (!hasChanges) return null
  return (
    <div className="flex items-center rounded-lg border bg-background/95 px-2 py-1.5 shadow-sm">
      <ToggleGroup type="single" variant="outline" size="sm" spacing={0} value={view} onValueChange={(v) => v && setView(v as MapView)} aria-label="Map shows">
        <ToggleGroupItem value="today" className="px-3">Today</ToggleGroupItem>
        <ToggleGroupItem value="scenario" className="px-3">{SCENARIO_LABEL[mode]}</ToggleGroupItem>
      </ToggleGroup>
    </div>
  )
}
