// Mock stand-in for engine.rescore(area, changes): one routine for Repair
// interventions and Protect buildings (ARCHITECTURE.md rule 2). Applies each
// change's effects, recomputes block PSS from footpath shade and the area scores
// with the ACS formula from docs/PLANNING.md. Mock values only.

import type { AreaResult, AreaScores, BlockResult, Change, IndexDelta, IndexKey, RiskLabel, Scores, ShadeByTime, TimeToBenefit, UnitCosts } from '../types'
import type { AreaIndex } from './areaIndex'
import { buildingEffects, designOf } from './buildingEffects'

const VENTILATION_LIMIT = 10
const RISK = { moderate: 10, high: 25 }

const clamp = (v: number) => Math.max(0, Math.min(100, v))
const round1 = (v: number) => Math.round(v * 10) / 10
const shadeShare = (s: ShadeByTime) => s.filter(Boolean).length / s.length
const blockCooling = (s: Scores) => 0.45 * (100 - s.hei) + 0.35 * s.pss + 0.2 * s.gcs

/** Interventions that help this summer: within weeks or one season. */
export function isQuickWin(timeToBenefit: TimeToBenefit) {
  return timeToBenefit !== 'years'
}

export function riskLabel(worst: number): RiskLabel {
  return worst >= RISK.high ? 'HIGH' : worst >= RISK.moderate ? 'MODERATE' : 'LOW'
}

/** Harm per index (positive = worse), so the worst change is the largest. */
function harms(before: Scores, after: Scores): Record<IndexKey, number> {
  return { vci: before.vci - after.vci, hei: after.hei - before.hei, gcs: before.gcs - after.gcs, pss: before.pss - after.pss }
}

export function rescoreMock(index: AreaIndex, changes: Change[], unitCosts: UnitCosts): AreaResult {
  const newShade: Record<string, ShadeByTime> = {}
  const blockDelta = new Map<string, IndexDelta>()
  const drivers = new Set<string>()
  const buildingBlocks: { parcelId: string; blockId: string }[] = []
  let costInr = 0
  let quickWinCostInr = 0
  let ventilationFlagged = false
  const waitPoints = new Set<string>()

  const addShade = (effects: Record<string, ShadeByTime>) => {
    for (const [segId, add] of Object.entries(effects)) {
      const base = newShade[segId] ?? index.segmentById.get(segId)?.shaded ?? [false, false, false]
      newShade[segId] = base.map((v, i) => v || add[i]) as ShadeByTime
    }
  }
  const addBlocks = (effects: Record<string, IndexDelta>) => {
    for (const [id, d] of Object.entries(effects)) {
      const acc = blockDelta.get(id) ?? { hei: 0, gcs: 0, vci: 0 }
      blockDelta.set(id, { hei: acc.hei + d.hei, gcs: acc.gcs + d.gcs, vci: acc.vci + d.vci })
    }
  }

  for (const change of changes) {
    if (change.kind === 'building') {
      const parcel = index.parcelById.get(change.siteId)
      if (!parcel) continue
      const effect = buildingEffects(index, parcel, designOf(change.params, change.quantity))
      addShade(effect.segments)
      addBlocks(effect.blocks)
      effect.drivers.forEach((d) => drivers.add(d))
      buildingBlocks.push({ parcelId: parcel.id, blockId: parcel.blockId })
      continue
    }
    const site = index.siteById.get(change.siteId)
    if (!site) continue
    addShade(site.effects.segments)
    addBlocks(site.effects.blocks)
    site.drivers.forEach((d) => drivers.add(d))
    if (!site.ventilation.ok) ventilationFlagged = true
    if (site.waitPoint) waitPoints.add(site.waitPoint)
    const cost = change.quantity * unitCosts[site.type].inr
    costInr += cost
    if (isQuickWin(site.timeToBenefit)) quickWinCostInr += cost
  }

  const blocks: BlockResult[] = []
  const afterById = new Map<string, Scores>()
  const before = { vci: 0, hei: 0, gcs: 0, pss: 0, acs: 0 }
  const after = { vci: 0, hei: 0, gcs: 0, pss: 0, acs: 0 }
  let weight = 0
  let worstVciDrop = 0
  let blocksWorse = 0
  for (const b of index.blocks) {
    const d = blockDelta.get(b.id)
    const segs = index.segmentsByBlock.get(b.id) ?? []
    const touched = segs.some((s) => newShade[s.id])
    let pss = b.scores.pss
    if (touched) {
      const len = segs.reduce((a, s) => a + s.lengthM, 0)
      pss = len ? (100 * segs.reduce((a, s) => a + s.lengthM * shadeShare(newShade[s.id] ?? s.shaded), 0)) / len : pss
    }
    const scores: Scores = {
      vci: round1(clamp(b.scores.vci + (d?.vci ?? 0))),
      hei: round1(clamp(b.scores.hei + (d?.hei ?? 0))),
      gcs: round1(clamp(b.scores.gcs + (d?.gcs ?? 0))),
      pss: round1(clamp(pss)),
    }
    afterById.set(b.id, scores)
    if (d || touched) blocks.push({ id: b.id, before: b.scores, after: scores })
    worstVciDrop = Math.max(worstVciDrop, b.scores.vci - scores.vci)
    if (blockCooling(scores) < blockCooling(b.scores) - 0.5) blocksWorse++
    const w = (1 + Math.min(2, b.waitWeight / 3)) * (b.builtForm === 'dense_low_rise' ? 1.25 : 1)
    weight += w
    accumulate(before, b.scores, w)
    accumulate(after, scores, w)
  }

  const result: AreaResult = {
    before: finalize(before, weight),
    after: finalize(after, weight),
    blocks,
    segments: newShade,
    ventilationOk: worstVciDrop < VENTILATION_LIMIT && !ventilationFlagged,
    worstVciDrop: round1(worstVciDrop),
    waitPointsCovered: waitPoints.size,
    costInr,
    quickWinCostInr,
    drivers: [...drivers],
    blocksWorse,
  }
  if (buildingBlocks.length) {
    const parcelRisk: NonNullable<AreaResult['parcelRisk']> = {}
    for (const { parcelId, blockId } of buildingBlocks) {
      const b = index.blockById.get(blockId)
      const a = afterById.get(blockId)
      if (!b || !a) continue
      const [key, change] = (Object.entries(harms(b.scores, a)) as [IndexKey, number][]).reduce((x, y) => (y[1] > x[1] ? y : x))
      parcelRisk[parcelId] = { label: riskLabel(change), index: key, change: round1(Math.max(0, change)) }
    }
    result.parcelRisk = parcelRisk
    result.risk = Object.values(parcelRisk).reduce((x, y) => (y.change > x.change ? y : x))
  }
  return result
}

function accumulate(target: AreaScores, s: Scores, w: number) {
  target.vci += w * s.vci
  target.hei += w * s.hei
  target.gcs += w * s.gcs
  target.pss += w * s.pss
  target.acs += w * blockCooling(s)
}

function finalize(sum: AreaScores, w: number): AreaScores {
  return { vci: round1(sum.vci / w), hei: round1(sum.hei / w), gcs: round1(sum.gcs / w), pss: round1(sum.pss / w), acs: round1(sum.acs / w) }
}
