import type { Mode } from '@/api/types'
import type { StepState } from '@/components/StepCard'
import { useUiStore } from './uiStore'

/** Step state for the current mode: exactly one open step; later unreached steps are locked. */
export function useSteps(mode: Mode) {
  const open = useUiStore((s) => s.openStep[mode])
  const reached = useUiStore((s) => s.reachedStep[mode])
  const openStepAt = useUiStore((s) => s.openStepAt)
  const advance = useUiStore((s) => s.advance)
  const stateOf = (index: number): StepState => (index === open ? 'open' : index <= reached ? 'done' : 'locked')
  return { stateOf, edit: openStepAt, advance }
}
