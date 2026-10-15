import { useMemo } from 'react'
import { useArea, useSites } from '@/api/hooks'
import type { InterventionType, Site } from '@/api/types'
import { BriefSection, BriefSheet } from '@/components/BriefSheet'
import { formatDelta, formatInr, formatScore } from '@/lib/format'
import { INDEX_META, INDEX_ORDER, INTERVENTION_META, PHASE, TIME_TO_BENEFIT_LABEL, driverLabel } from '@/lib/meta'
import { useScenario } from '@/state/useScenario'
import { useRepairStore } from './repairStore'
import type { RepairPlan } from './useRepairPlan'

const LAKH = 1e5

/** The printable cooling plan: outcome, phased interventions, field checks, rejected options. */
export function RepairBrief({ plan }: { plan: RepairPlan }) {
  const { areaId, changes, rejected, result } = useScenario()
  const budgetLakh = useRepairStore((s) => s.budgetLakh)
  const { data: area } = useArea(areaId)
  const { data: siteList } = useSites(areaId)
  const sites = useMemo(() => new Map((siteList ?? []).map((s) => [s.id, s])), [siteList])
  if (!area || !result) return null

  const chosen = changes.map((c) => ({ change: c, site: sites.get(c.siteId) })).filter((x): x is { change: typeof x.change; site: Site } => !!x.site)
  const phases = [...new Set(chosen.map((x) => x.site.timeToBenefit))].sort((a, b) => PHASE[a].order - PHASE[b].order)
  const types = [...new Set(chosen.map((x) => x.site.type))] as InterventionType[]

  return (
    <BriefSheet title={`Cooling plan: ${area.name}, ${area.city}`} subtitle={`Budget ${formatInr(budgetLakh * LAKH)} · plan cost ${formatInr(result.costInr)}, of which ${formatInr(result.quickWinCostInr)} helps this summer · ${chosen.length} interventions`}>
      <BriefSection title="Outcome">
        <table className="w-full text-left">
          <thead><tr className="border-b"><th className="py-1">Score</th><th>Today</th><th>With plan</th><th>Change</th></tr></thead>
          <tbody>
            {INDEX_ORDER.map((k) => (
              <tr key={k} className="border-b">
                <td className="py-1">{INDEX_META[k].label}</td>
                <td>{formatScore(result.before[k])}</td>
                <td>{formatScore(result.after[k])}</td>
                <td>{formatDelta(result.after[k] - result.before[k])}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {plan.result && <p>{plan.result.explanation.paragraphs.join(' ')}</p>}
      </BriefSection>

      {phases.map((phase) => (
        <BriefSection key={phase} title={`${PHASE[phase].title} (${TIME_TO_BENEFIT_LABEL[phase].toLowerCase()} to benefit)`}>
          <ul className="list-disc space-y-1 pl-5">
            {chosen.filter((x) => x.site.timeToBenefit === phase).map(({ change, site }) => (
              <li key={site.id}>
                {site.name}: {formatInr(change.quantity * site.unitCost.inr)}. {site.drivers.map(driverLabel).join(', ')}.
              </li>
            ))}
          </ul>
        </BriefSection>
      ))}

      <BriefSection title="Field checks before work starts">
        {types.map((t) => (
          <div key={t}>
            <p className="font-semibold">{INTERVENTION_META[t].label}</p>
            <ul className="list-disc pl-5">{INTERVENTION_META[t].fieldChecks.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        ))}
      </BriefSection>

      {rejected.length > 0 && (
        <BriefSection title="Rejected options">
          <ul className="list-disc space-y-1 pl-5">
            {rejected.map((r) => <li key={r.siteId}>{sites.get(r.siteId)?.name}: {r.reason}</li>)}
          </ul>
        </BriefSection>
      )}
    </BriefSheet>
  )
}
