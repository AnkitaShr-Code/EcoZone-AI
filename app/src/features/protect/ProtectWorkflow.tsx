import { MousePointerClick } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { StepCard } from '@/components/StepCard'
import { useSteps } from '@/state/useSteps'

/** Protect: parcel → proposal → compare designs → build-out → brief (UI_RULES.md §3). */
export function ProtectWorkflow() {
  const { stateOf } = useSteps('protect')
  return (
    <div className="space-y-3">
      <StepCard
        number={1}
        title="Choose parcel"
        state={stateOf(0)}
        instruction="Select a vacant parcel on the map to test a proposed building on it."
        primary={{ label: 'Use this parcel', onClick: () => undefined, disabled: true, disabledReason: 'Parcel selection is built in the next pass.' }}
      >
        <EmptyState icon={MousePointerClick}>Candidate parcels will be highlighted on the map.</EmptyState>
      </StepCard>
      <StepCard number={2} title="Describe proposal" state={stateOf(1)} lockedReason="Choose a parcel first" />
      <StepCard number={3} title="Compare designs" state={stateOf(2)} lockedReason="Describe the proposal first" />
      <StepCard number={4} title="Check build-out" state={stateOf(3)} lockedReason="Optional. Compare designs first" />
      <StepCard number={5} title="Export brief" state={stateOf(4)} lockedReason="Choose a design first" />
    </div>
  )
}
