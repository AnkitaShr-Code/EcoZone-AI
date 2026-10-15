// Mock stand-in for the Planning Advisor's explanations. Every number in the
// text comes from an engine result or planner input in the same call, which is
// what the real output guard enforces (docs/PLANNING.md, grounding rules).

import { formatInr, formatScore } from '@/lib/format'
import { INTERVENTION_META, driverLabel } from '@/lib/meta'
import type { AreaResult, Candidate, Change, DesignOption, Explanation, IndexKey, InterventionType, ParcelProps, RiskInfo, UnitCosts } from '../types'
import type { AreaIndex } from './areaIndex'
import { designOf } from './buildingEffects'
import { rescoreMock } from './rescoreMock'

const INDEX_WORDS: Record<IndexKey, { name: string; worse: string }> = {
  vci: { name: 'ventilation', worse: 'falls' },
  hei: { name: 'heat exposure', worse: 'rises' },
  gcs: { name: 'green connectivity', worse: 'falls' },
  pss: { name: 'footpath shade', worse: 'falls' },
}

export function explainPlan(index: AreaIndex, chosen: Candidate, result: AreaResult, greedy: Candidate, rejectedCount: number, budgetInr: number): Explanation {
  const counts = new Map<InterventionType, number>()
  for (const ch of chosen.changes) {
    const site = index.siteById.get(ch.siteId)
    if (site) counts.set(site.type, (counts.get(site.type) ?? 0) + 1)
  }
  const mix = [...counts.entries()].map(([t, c]) => `${c} ${(c === 1 ? INTERVENTION_META[t].label : INTERVENTION_META[t].plural).toLowerCase()}`)
  const paragraphs = [
    `This plan raises the area cooling score from ${formatScore(result.before.acs)} to ${formatScore(result.after.acs)}, using ${formatInr(result.costInr)} of the ${formatInr(budgetInr)} budget.`,
    `It combines ${listWords(mix)}. Footpath shade goes from ${formatScore(result.before.pss)} to ${formatScore(result.after.pss)}${result.waitPointsCovered ? `, and ${result.waitPointsCovered} waiting points get shade at their entrance` : ''}.`,
  ]
  if (rejectedCount) paragraphs.push(`${rejectedCount} tree rows near the hotspots were left out: the streets are deep and narrow, so canopy there would block the breeze. A shade structure works better on those streets.`)
  paragraphs.push(chosen.source === 'greedy'
    ? `No AI plan beat the simple ranking baseline, so the baseline plan is shown (${formatScore(greedy.score)}).`
    : `The simple ranking baseline reaches ${formatScore(greedy.score)}; this plan reaches ${formatScore(chosen.score)}.`)
  return { paragraphs, drivers: result.drivers, source: 'gemini' }
}

export function explainDesigns(index: AreaIndex, parcel: ParcelProps, options: DesignOption[]): Explanation {
  const [a, b, c] = options
  const risk = riskOf(index, a.candidate.changes)
  const paragraphs = risk ? [riskSentence(risk, a.design.floors, parcel)] : []
  paragraphs.push(
    `Option B keeps ${b.candidate.floorAreaPct}% of the floor area and brings the worst change from ${formatScore(a.candidate.score)} to ${formatScore(b.candidate.score)}.`,
    `Option C keeps ${c.candidate.floorAreaPct}% of the floor area and brings it to ${formatScore(c.candidate.score)}. The planner decides which trade-off fits.`,
  )
  return { paragraphs, drivers: rescoreMock(index, a.candidate.changes, index.area.unitCostDefaults).drivers, source: 'gemini' }
}

/** Explanation for any change set: a proposal (Protect) or a plan (Repair). */
export function explainChanges(index: AreaIndex, changes: Change[], unitCosts: UnitCosts): Explanation {
  const result = rescoreMock(index, changes, unitCosts)
  const building = changes.find((c) => c.kind === 'building')
  if (building && result.risk) {
    const parcel = index.parcelById.get(building.siteId) as ParcelProps
    const design = designOf(building.params, building.quantity)
    const paragraphs = [riskSentence(result.risk, design.floors, parcel)]
    const main = result.drivers.filter((d) => d !== 'SHADE_GAIN').map(driverLabel)
    if (main.length) paragraphs.push(`Main drivers: ${listWords(main.map((d) => d.toLowerCase()))}.`)
    if (result.drivers.includes('SHADE_GAIN')) paragraphs.push(`The building also shades nearby footpath, so footpath shade rises from ${formatScore(result.before.pss)} to ${formatScore(result.after.pss)} across the area.`)
    if (result.blocksWorse) paragraphs.push(`${result.blocksWorse} existing blocks around the parcel lose cooling score.`)
    return { paragraphs, drivers: result.drivers, source: 'gemini' }
  }
  return {
    paragraphs: [`These changes move the area cooling score from ${formatScore(result.before.acs)} to ${formatScore(result.after.acs)}.`],
    drivers: result.drivers,
    source: 'gemini',
  }
}

function riskOf(index: AreaIndex, changes: Change[]) {
  return rescoreMock(index, changes, index.area.unitCostDefaults).risk
}

function riskSentence(risk: RiskInfo, floors: number, parcel: ParcelProps) {
  const words = INDEX_WORDS[risk.index]
  return `As proposed, the worst effect is on ${words.name}: it ${words.worse} by ${formatScore(risk.change)} on the parcel's block (${risk.label.toLowerCase()} risk). A ${floors}-floor building faces a ${parcel.roadWidthM} m street.`
}

function listWords(items: string[]) {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
