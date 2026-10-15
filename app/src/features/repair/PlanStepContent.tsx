import { useMemo } from 'react'
import { useArea, useSites } from '@/api/hooks'
import { changesKey } from '@/api/keys'
import { ExplanationCard } from '@/components/ExplanationCard'
import { ScoreChanges } from '@/components/ScoreChanges'
import { SearchProgress } from '@/components/SearchProgress'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, formatScore } from '@/lib/format'
import { useScenario } from '@/state/useScenario'
import { PlanTable } from './PlanTable'
import { RejectedList } from './RejectedList'
import type { RepairPlan } from './useRepairPlan'

/** Step 3: live search, then the plan with its scores, explanation and rejected options. */
export function PlanStepContent({ plan, budgetInr, quickWinSharePct }: { plan: RepairPlan; budgetInr: number; quickWinSharePct: number }) {
  const { areaId, changes, rejected, result: scores, unitCosts } = useScenario()
  const { data: area } = useArea(areaId)
  const { data: siteList } = useSites(areaId)
  const sites = useMemo(() => new Map((siteList ?? []).map((s) => [s.id, s])), [siteList])

  const progress = (
    <SearchProgress
      state={plan.state}
      running={plan.running}
      failed={plan.failed}
      scoreLabel="Area cooling score after each plan"
      formatScore={(c) => formatScore(c.score)}
      isBetter={(a, b) => a.score > b.score}
      baselineLabel="Baseline: best gain per rupee"
      onStop={plan.stop}
    />
  )
  if (!plan.applied) return progress

  const drafted = plan.result?.best.changes ?? changes
  const edited = !!plan.result && changesKey(changes) !== changesKey(plan.result.best.changes)
  const cost = scores?.costInr ?? 0
  const quickWins = scores?.quickWinCostInr ?? 0
  const quickWinTarget = (budgetInr * quickWinSharePct) / 100

  return (
    <div className="space-y-4">
      <details className="group rounded-lg">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          {plan.result
            ? plan.result.geminiBeatGreedy ? 'AI plan beat the simple baseline. Show search details' : 'The simple baseline won. Show search details'
            : 'Search stopped early. Show search details'}
        </summary>
        <div className="mt-2">{progress}</div>
      </details>

      {area && scores ? (
        <ScoreChanges before={area.baseline} after={scores.after} indices={['acs', 'pss', 'hei', 'gcs']} />
      ) : (
        <Skeleton className="h-36 w-full" />
      )}

      <dl className="space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Cost</dt>
          <dd className={cost > budgetInr ? 'font-semibold text-delta-worse' : 'font-semibold'}>{formatInr(cost)} of {formatInr(budgetInr)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Helps this summer</dt>
          <dd className={quickWins < quickWinTarget ? 'text-delta-worse' : ''}>{formatInr(quickWins)} (needs {formatInr(quickWinTarget)})</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Ventilation check</dt>
          <dd className={scores?.ventilationOk === false ? 'text-delta-worse' : ''}>{scores?.ventilationOk === false ? 'Fails' : 'Passes'}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Waiting points shaded</dt>
          <dd>{scores?.waitPointsCovered ?? 0}</dd>
        </div>
      </dl>

      {plan.result && (
        <ExplanationCard explanation={plan.result.explanation} staleNote={edited ? 'You have edited the plan since this was written.' : undefined} />
      )}

      {unitCosts && (
        <div>
          <h3 className="mb-1.5 text-sm font-semibold">Interventions ({changes.length})</h3>
          <PlanTable drafted={drafted} included={changes} sites={sites} unitCosts={unitCosts} />
        </div>
      )}

      <RejectedList rejected={rejected} sites={sites} />
    </div>
  )
}
