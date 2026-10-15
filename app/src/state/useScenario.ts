import { useArea, useRescore } from '@/api/hooks'
import { useCostsStore } from './costsStore'
import { useScenarioStore } from './scenarioStore'
import { useUiStore } from './uiStore'

/** The current mode's working scenario and its engine scores. */
export function useScenario() {
  const areaId = useUiStore((s) => s.areaId)
  const mode = useUiStore((s) => s.mode)
  const { changes, rejected } = useScenarioStore((s) => s.scenario[mode])
  const view = useScenarioStore((s) => s.view)
  const { data: area } = useArea(areaId)
  const unitCosts = useCostsStore((s) => s.unitCosts) ?? area?.unitCostDefaults
  const rescore = useRescore(areaId, changes, unitCosts)
  return {
    areaId,
    mode,
    changes,
    rejected,
    view,
    unitCosts,
    result: changes.length ? rescore.data : undefined,
    isScoring: rescore.isFetching,
  }
}
