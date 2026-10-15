// Mock stand-in for engine.rescore(area, changes). Applies each site's
// precomputed effects and recomputes the area scores with the ACS formula from
// docs/PLANNING.md. Mock values only; the real engine replaces this.

import type { FeatureCollection, LineString, Polygon } from 'geojson'
import type { AreaResult, AreaScores, AreaSummary, BlockProps, BlockResult, Change, Scores, SegmentProps, ShadeByTime, Site, UnitCosts } from '../types'

const VENTILATION_LIMIT = 10

interface Input {
  area: AreaSummary
  blocks: FeatureCollection<Polygon, BlockProps>
  segments: FeatureCollection<LineString, SegmentProps>
  sites: Site[]
  changes: Change[]
  unitCosts: UnitCosts
}

const clamp = (v: number) => Math.max(0, Math.min(100, v))
const round1 = (v: number) => Math.round(v * 10) / 10
const shadeShare = (s: ShadeByTime) => s.filter(Boolean).length / s.length

function blockCooling(s: Scores): number {
  return 0.45 * (100 - s.hei) + 0.35 * s.pss + 0.2 * s.gcs
}

function weightOf(p: BlockProps): number {
  const exposure = 1 + Math.min(2, p.waitWeight / 3)
  return exposure * (p.builtForm === 'dense_low_rise' ? 1.25 : 1)
}

export function rescoreMock({ area, blocks, segments, sites, changes, unitCosts }: Input): AreaResult {
  const siteById = new Map(sites.map((s) => [s.id, s]))
  const chosen = changes.map((c) => siteById.get(c.siteId)).filter((s): s is Site => !!s)

  // New shade state per segment (OR of baseline and every chosen site's effect).
  const newShade: Record<string, ShadeByTime> = {}
  const segById = new Map(segments.features.map((f) => [f.properties.id, f.properties]))
  for (const site of chosen) {
    for (const [segId, add] of Object.entries(site.effects.segments)) {
      const base = newShade[segId] ?? segById.get(segId)?.shaded ?? [false, false, false]
      newShade[segId] = base.map((v, i) => v || add[i]) as ShadeByTime
    }
  }

  // Block index deltas from site effects; PSS recomputed from segment shade.
  const blockDelta = new Map<string, { hei: number; gcs: number; vci: number }>()
  for (const site of chosen) {
    for (const [blockId, d] of Object.entries(site.effects.blocks)) {
      const acc = blockDelta.get(blockId) ?? { hei: 0, gcs: 0, vci: 0 }
      blockDelta.set(blockId, { hei: acc.hei + d.hei, gcs: acc.gcs + d.gcs, vci: acc.vci + d.vci })
    }
  }
  const segsByBlock = new Map<string, SegmentProps[]>()
  for (const f of segments.features) {
    if (!f.properties.block) continue
    const list = segsByBlock.get(f.properties.block) ?? []
    list.push(f.properties)
    segsByBlock.set(f.properties.block, list)
  }

  const results: BlockResult[] = []
  let worstVciDrop = 0
  const acc = { before: { vci: 0, hei: 0, gcs: 0, pss: 0, acs: 0 }, after: { vci: 0, hei: 0, gcs: 0, pss: 0, acs: 0 }, w: 0 }
  for (const f of blocks.features) {
    const p = f.properties
    const d = blockDelta.get(p.id)
    const segs = segsByBlock.get(p.id) ?? []
    const touched = segs.some((s) => newShade[s.id])
    let pss = p.scores.pss
    if (touched) {
      const len = segs.reduce((a, s) => a + s.lengthM, 0)
      pss = len ? (100 * segs.reduce((a, s) => a + s.lengthM * shadeShare(newShade[s.id] ?? s.shaded), 0)) / len : pss
    }
    const after: Scores = {
      vci: clamp(p.scores.vci + (d?.vci ?? 0)),
      hei: clamp(p.scores.hei + (d?.hei ?? 0)),
      gcs: clamp(p.scores.gcs + (d?.gcs ?? 0)),
      pss: clamp(pss),
    }
    if (d || touched) results.push({ id: p.id, before: p.scores, after: mapRound(after) })
    worstVciDrop = Math.max(worstVciDrop, p.scores.vci - after.vci)
    const w = weightOf(p)
    acc.w += w
    accumulate(acc.before, p.scores, w)
    accumulate(acc.after, after, w)
  }

  const coveredWaitPoints = new Set(chosen.map((s) => s.waitPoint).filter(Boolean))
  return {
    before: area.baseline,
    after: finalize(acc.after, acc.w),
    blocks: results,
    segments: newShade,
    ventilationOk: worstVciDrop < VENTILATION_LIMIT && chosen.every((s) => s.ventilation.ok),
    worstVciDrop: round1(worstVciDrop),
    waitPointsCovered: coveredWaitPoints.size,
    costInr: changes.reduce((sum, c) => {
      const site = siteById.get(c.siteId)
      return site ? sum + c.quantity * unitCosts[site.type].inr : sum
    }, 0),
    drivers: [...new Set(chosen.flatMap((s) => s.drivers))],
  }
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

function mapRound(s: Scores): Scores {
  return { vci: round1(s.vci), hei: round1(s.hei), gcs: round1(s.gcs), pss: round1(s.pss) }
}
