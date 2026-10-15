import { useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { useArea } from '@/api/hooks'
import type { InterventionType } from '@/api/types'
import { Provenance } from '@/components/Provenance'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { INTERVENTION_META } from '@/lib/meta'
import { useUiStore } from '@/state/uiStore'
import { useRepairStore } from './repairStore'

/** Step 2: the rupee budget and unit costs the plan search will use. */
export function BudgetStepContent() {
  const areaId = useUiStore((s) => s.areaId)
  const { data: area } = useArea(areaId)
  const { budgetLakh, unitCosts, edited, setBudgetLakh, initUnitCosts, setUnitCost } = useRepairStore()

  useEffect(() => {
    if (area) initUnitCosts(area.unitCostDefaults)
  }, [area, initUnitCosts])

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="budget">Total budget</Label>
          <Provenance kind="planner" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">₹</span>
          <Input
            id="budget"
            type="number"
            inputMode="decimal"
            min={1}
            step={1}
            value={budgetLakh}
            onChange={(e) => setBudgetLakh(Number(e.target.value))}
            className="tabular-nums"
          />
          <span className="text-sm text-muted-foreground">lakh</span>
        </div>
      </div>

      <details className="group rounded-lg border">
        <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-sm font-semibold">
          Unit costs
          <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <ul className="space-y-2.5 border-t px-3 py-3">
          {unitCosts && (Object.keys(unitCosts) as InterventionType[]).map((type) => {
            const meta = INTERVENTION_META[type]
            const Icon = meta.icon
            return (
              <li key={type} className="grid grid-cols-[1fr_7rem] items-center gap-2">
                <Label htmlFor={`cost-${type}`} className="flex items-center gap-2 font-normal">
                  <Icon className="size-4 text-muted-foreground" aria-hidden />
                  <span>
                    {meta.label}
                    <span className="block text-xs text-muted-foreground">
                      per {unitCosts[type].unit} · <Provenance kind={edited[type] ? 'planner' : 'default'} className="py-0" />
                    </span>
                  </span>
                </Label>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground">₹</span>
                  <Input
                    id={`cost-${type}`}
                    type="number"
                    min={0}
                    value={unitCosts[type].inr}
                    onChange={(e) => setUnitCost(type, Number(e.target.value))}
                    className="h-8 tabular-nums"
                  />
                </div>
              </li>
            )
          })}
        </ul>
        <p className="border-t px-3 py-2 text-xs text-muted-foreground">Costs are planner inputs for comparing options, not market prices.</p>
      </details>
    </div>
  )
}
