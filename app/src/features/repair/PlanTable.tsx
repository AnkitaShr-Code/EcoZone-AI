import { ChevronDown } from 'lucide-react'
import { isInterventionChange } from '@/api/changes'
import type { Change, InterventionChange, InterventionType, Site, UnitCosts } from '@/api/types'
import { Checkbox } from '@/components/ui/checkbox'
import { formatInr } from '@/lib/format'
import { centerOf } from '@/lib/geo'
import { INTERVENTION_META, TIME_TO_BENEFIT_LABEL, driverLabel } from '@/lib/meta'
import { flyTo } from '@/map/mapController'
import { useScenarioStore } from '@/state/scenarioStore'
import { useUiStore } from '@/state/uiStore'

const TYPE_ORDER: InterventionType[] = ['shade', 'cool_roof', 'depave', 'pocket_green', 'tree_row']
const OPEN_GROUP_MAX = 6

interface PlanTableProps {
  /** Every item the search put in the plan; the planner can untick any of them. */
  drafted: Change[]
  included: Change[]
  sites: Map<string, Site>
  unitCosts: UnitCosts
}

/**
 * The plan as a list, grouped by intervention type: the map's list equivalent (UI_RULES.md §9).
 * Unticking an item rescores instantly.
 */
export function PlanTable({ drafted, included, sites, unitCosts }: PlanTableProps) {
  const isIncluded = new Set(included.map((c) => c.siteId))
  const rows = drafted.filter(isInterventionChange).map((change) => ({ change, site: sites.get(change.siteId) }))
    .filter((r): r is { change: InterventionChange; site: Site } => !!r.site)
  const groups = TYPE_ORDER.map((type) => ({ type, rows: rows.filter((r) => r.site.type === type) })).filter((g) => g.rows.length)

  return (
    <div className="space-y-2" aria-label="Interventions in the plan">
      {groups.map(({ type, rows: groupRows }) => {
        const meta = INTERVENTION_META[type]
        const Icon = meta.icon
        const on = groupRows.filter((r) => isIncluded.has(r.site.id))
        const subtotal = on.reduce((sum, r) => sum + r.change.quantity * unitCosts[type].inr, 0)
        return (
          <details key={type} open={groupRows.length <= OPEN_GROUP_MAX} className="group rounded-lg border">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm">
              <Icon className="size-4 shrink-0" style={{ color: `var(--${meta.color})` }} aria-hidden />
              <span className="flex-1 font-semibold">{meta.plural} · {on.length} of {groupRows.length}</span>
              <span className="tabular-nums text-muted-foreground">{formatInr(subtotal)}</span>
              <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <ul className="divide-y border-t">
              {groupRows.map(({ change, site }) => <PlanRow key={site.id} change={change} site={site} included={isIncluded.has(site.id)} unitCosts={unitCosts} />)}
            </ul>
          </details>
        )
      })}
    </div>
  )
}

function PlanRow({ change, site, included, unitCosts }: { change: InterventionChange; site: Site; included: boolean; unitCosts: UnitCosts }) {
  const toggleChange = useScenarioStore((s) => s.toggleChange)
  const select = useUiStore((s) => s.select)
  return (
    <li className="flex items-start gap-3 px-3 py-2">
      <Checkbox
        checked={included}
        onCheckedChange={() => toggleChange('repair', change)}
        aria-label={`${included ? 'Remove' : 'Add back'} ${site.name}`}
        className="mt-0.5"
      />
      <div className="min-w-0 flex-1">
        <button
          type="button"
          className={`text-left text-sm hover:underline ${included ? '' : 'text-muted-foreground line-through'}`}
          onClick={() => {
            select({ kind: 'site', id: site.id })
            flyTo(centerOf(site.geometry), 17.5)
          }}
        >
          {site.name.replace(/^[^,]+, /, '')}
        </button>
        <p className="text-xs text-muted-foreground">
          {formatInr(change.quantity * unitCosts[site.type].inr)} · {TIME_TO_BENEFIT_LABEL[site.timeToBenefit]} · {site.singleSite.drivers.map(driverLabel).join(', ')}
        </p>
      </div>
    </li>
  )
}
