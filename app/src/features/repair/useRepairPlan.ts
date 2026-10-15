import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSearchRun, type SearchState } from '@/api/hooks'
import type { Candidate } from '@/api/types'
import { useScenarioStore } from '@/state/scenarioStore'
import { useUiStore } from '@/state/uiStore'
import { useRepairStore } from './repairStore'

/**
 * The Repair plan search and its hand-off to the working plan. Lives in the workflow
 * (not a step) so a running search survives opening another step.
 */
export function useRepairPlan() {
  const areaId = useUiStore((s) => s.areaId)
  const run = useRepairStore((s) => s.run)
  const appliedRunId = useRepairStore((s) => s.appliedRunId)
  const markApplied = useRepairStore((s) => s.markApplied)
  const setChanges = useScenarioStore((s) => s.setChanges)
  const queryClient = useQueryClient()
  const search = useSearchRun(areaId, run?.request ?? null, run?.id ?? null)
  const result = search.data?.result ?? null

  // When a run finishes, its best plan becomes the working plan once.
  useEffect(() => {
    if (run && result && appliedRunId !== run.id) {
      setChanges('repair', result.best.changes, result.rejected)
      markApplied(run.id)
    }
  }, [run, result, appliedRunId, setChanges, markApplied])

  const stop = () => {
    if (!run) return
    void queryClient.cancelQueries({ queryKey: ['search', areaId, run.id] })
    const best = bestSoFar(search.data)
    if (best) setChanges('repair', best.changes, [])
    markApplied(run.id)
  }

  const applied = !!run && appliedRunId === run.id
  return { run, state: search.data, result, running: !!run && search.isFetching && !applied, failed: search.isError, applied, stop }
}

export type RepairPlan = ReturnType<typeof useRepairPlan>

function bestSoFar(state: SearchState | undefined): Candidate | null {
  const all = [...(state?.rounds.flatMap((r) => r.candidates) ?? []), ...(state?.baseline ? [state.baseline] : [])]
  return all.filter((c) => c.valid).reduce<Candidate | null>((a, c) => (!a || c.score > a.score ? c : a), null)
}
