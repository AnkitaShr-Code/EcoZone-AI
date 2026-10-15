import { FileText } from 'lucide-react'
import { useArea } from '@/api/hooks'
import { EmptyState } from '@/components/EmptyState'
import { StepCard } from '@/components/StepCard'
import { formatCount, formatInr } from '@/lib/format'
import { useCostsStore } from '@/state/costsStore'
import { useScenario } from '@/state/useScenario'
import { useSteps } from '@/state/useSteps'
import { AreaStepContent } from './AreaStepContent'
import { BudgetStepContent } from './BudgetStepContent'
import { PlanStepContent } from './PlanStepContent'
import { RepairBrief } from './RepairBrief'
import { useRepairStore } from './repairStore'
import { useRepairPlan } from './useRepairPlan'

const LAKH = 1e5

/** Repair: choose area → set budget → review plan → export brief (UI_RULES.md §3). */
export function RepairWorkflow() {
  const { areaId, changes, result } = useScenario()
  const { data: area } = useArea(areaId)
  const budgetLakh = useRepairStore((s) => s.budgetLakh)
  const quickWinSharePct = useRepairStore((s) => s.quickWinSharePct)
  const startSearch = useRepairStore((s) => s.startSearch)
  const unitCosts = useCostsStore((s) => s.unitCosts)
  const plan = useRepairPlan()
  const { stateOf, edit, advance } = useSteps('repair')
  const budgetInr = budgetLakh * LAKH
  const budgetValid = Number.isFinite(budgetLakh) && budgetLakh > 0
  const inputsChanged = !!plan.run && (plan.run.request.budgetInr !== budgetInr || plan.run.request.unitCosts !== unitCosts || plan.run.request.quickWinSharePct !== quickWinSharePct)
  const overBudget = (result?.costInr ?? 0) > budgetInr
  const belowQuickWins = !!result && result.quickWinCostInr < (budgetInr * quickWinSharePct) / 100
  const draft = () => {
    if (!unitCosts) return
    startSearch(unitCosts)
    if (stateOf(1) === 'open') advance()
    else edit(2)
  }

  return (
    <div className="space-y-3">
      <StepCard
        number={1}
        title="Choose area"
        state={stateOf(0)}
        summary={area ? `${area.name}, ${area.city}` : undefined}
        instruction="Check the area's scores and hotspots, then confirm it."
        primary={{ label: 'Use this area', onClick: advance, disabled: !area }}
        onEdit={() => edit(0)}
      >
        <AreaStepContent />
      </StepCard>

      <StepCard
        number={2}
        title="Set budget"
        state={stateOf(1)}
        summary={formatInr(budgetInr)}
        instruction="Enter the money available. The plan search will stay within it."
        lockedReason="Choose an area first"
        primary={{
          label: plan.run ? 'Draft the plan again' : 'Draft cooling plan',
          onClick: draft,
          disabled: !budgetValid || !unitCosts,
          disabledReason: 'Enter a budget above zero.',
        }}
        onEdit={() => edit(1)}
      >
        <BudgetStepContent />
      </StepCard>

      <StepCard
        number={3}
        title="Review plan"
        state={stateOf(2)}
        summary={result ? `${formatCount(changes.length, 'intervention')} · ${formatInr(result.costInr)}` : undefined}
        staleNote={inputsChanged ? 'Budget, quick-win share or costs changed. Draft the plan again.' : undefined}
        instruction={plan.applied ? 'Untick anything you want to leave out; scores update instantly. Click an item to see it on the map.' : 'Gemini is drafting options; the engine scores each one.'}
        lockedReason="Draft a plan first"
        primary={{
          label: 'Accept plan',
          onClick: advance,
          disabled: !plan.applied || !changes.length || overBudget || belowQuickWins,
          disabledReason: overBudget ? 'The plan is over budget. Untick an item.'
            : belowQuickWins ? 'Below the quick-win share. Tick a shade structure, cool roof or depave site.'
              : !changes.length ? 'Tick at least one intervention.' : 'Wait for the search to finish.',
        }}
        secondary={plan.applied ? { label: 'Draft again', onClick: draft } : undefined}
        onEdit={() => edit(2)}
      >
        <PlanStepContent plan={plan} budgetInr={budgetInr} quickWinSharePct={quickWinSharePct} />
      </StepCard>

      <StepCard
        number={4}
        title="Export brief"
        state={stateOf(3)}
        instruction="Download a printable cooling plan with phasing and field checks for the ward."
        lockedReason="Accept a plan first"
        primary={{ label: 'Download brief', onClick: () => window.print() }}
      >
        <EmptyState icon={FileText}>The brief lists the outcome, the work by season, field checks for each site, and the options that were rejected.</EmptyState>
        <RepairBrief plan={plan} />
      </StepCard>
    </div>
  )
}
