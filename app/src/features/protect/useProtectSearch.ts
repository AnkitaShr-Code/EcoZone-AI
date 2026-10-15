import { useQueryClient } from '@tanstack/react-query'
import { useSearchRun } from '@/api/hooks'
import { useUiStore } from '@/state/uiStore'
import { useProtectStore } from './protectStore'

/** The Protect design search. Lives in the workflow so a running search survives step changes. */
export function useProtectSearch() {
  const areaId = useUiStore((s) => s.areaId)
  const run = useProtectStore((s) => s.run)
  const queryClient = useQueryClient()
  const search = useSearchRun(areaId, run?.request ?? null, run?.id ?? null)
  const result = search.data?.result ?? null
  return {
    run,
    state: search.data,
    result,
    running: !!run && search.isFetching && !result,
    failed: search.isError,
    stop: () => run && queryClient.cancelQueries({ queryKey: ['search', areaId, run.id] }),
  }
}

export type ProtectSearch = ReturnType<typeof useProtectSearch>
