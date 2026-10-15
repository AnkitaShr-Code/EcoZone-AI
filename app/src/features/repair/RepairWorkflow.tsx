import { useArea } from '@/api/hooks'
import { StepCard } from '@/components/StepCard'
import { formatInr } from '@/lib/format'
import { useSteps } from '@/state/useSteps'
import { useUiStore } from '@/state/uiStore'
import { AreaStepContent } from './AreaStepContent'
import { BudgetStepContent } from './BudgetStepContent'
import { useRepairStore } from './repairStore'

const LAKH = 1e5

/** Repair: choose area → set budget → review plan → export brief (UI_RULES.md §3). */
export function RepairWorkflow() {
  const areaId = useUiStore((s) => s.areaId)
  const { data: area } = useArea(areaId)
  const budgetLakh = useRepairStore((s) => s.budgetLakh)
  const { stateOf, edit, advance } = useSteps('repair')
  const budgetValid = Number.isFinite(budgetLakh) && budgetLakh > 0

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
        summary={formatInr(budgetLakh * LAKH)}
        instruction="Enter the money available. The plan search will stay within it."
        lockedReason="Choose an area first"
        primary={{
          label: 'Draft cooling plan',
          onClick: advance,
          disabled: true,
          disabledReason: budgetValid ? 'Plan search is built in the next pass.' : 'Enter a budget above zero.',
        }}
        onEdit={() => edit(1)}
      >
        <BudgetStepContent />
      </StepCard>

      <StepCard number={3} title="Review plan" state={stateOf(2)} lockedReason="Draft a plan first" />
      <StepCard number={4} title="Export brief" state={stateOf(3)} lockedReason="Accept a plan first" />
    </div>
  )
}
