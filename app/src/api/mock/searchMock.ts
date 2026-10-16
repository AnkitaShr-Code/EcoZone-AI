// Mock stand-in for the agent search (agents/search.py): one propose → score →
// judge loop for both modes. The "proposer" here is a set of heuristics standing
// in for Gemini; every candidate is scored by rescoreMock, the engine stand-in.

import type { BuildingDesign, Candidate, Change, DesignOption, SearchEvent, SearchRequest, Site } from '../types'
import type { AreaIndex } from './areaIndex'
import { explainDesigns, explainPlan } from './explainMock'
import { isQuickWin, rescoreMock } from './rescoreMock'

const MAX_ROUNDS = 3
const STOP_THRESHOLD = { repair: 0.5, protect: 2 }
const ORIENTATION_STEP = 15
/** A worst-change gain smaller than this counts as no improvement. */
const NO_GAIN = 0.5

export function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException('Aborted', 'AbortError'))
    const t = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
}
const thinking = () => 260 + Math.random() * 260

export function searchMock(index: AreaIndex, request: SearchRequest, signal: AbortSignal): AsyncGenerator<SearchEvent> {
  return request.mode === 'repair' ? repairSearch(index, request, signal) : protectSearch(index, request, signal)
}

// ---------------- Repair: portfolio search against a greedy baseline ----------------

async function* repairSearch(index: AreaIndex, req: Extract<SearchRequest, { mode: 'repair' }>, signal: AbortSignal): AsyncGenerator<SearchEvent> {
  const { budgetInr, unitCosts } = req
  const quickWinTarget = (budgetInr * req.quickWinSharePct) / 100
  const base = index.area.baseline.acs
  const cost = (s: Site) => s.quantity * unitCosts[s.type].inr
  const changeOf = (s: Site): Change => ({ kind: s.type, siteId: s.id, quantity: s.quantity })
  const evaluate = (sites: Site[]) => rescoreMock(index, sites.map(changeOf), unitCosts)

  const affordable = index.sites.filter((s) => cost(s) <= budgetInr)
  const eligible = affordable.filter((s) => s.ventilation.ok)
  const gain = new Map(eligible.map((s) => [s.id, evaluate([s]).after.acs - base]))
  const ratio = (s: Site) => (gain.get(s.id) ?? 0) / Math.max(1, cost(s))
  const byRatio = [...eligible].sort((a, b) => ratio(b) - ratio(a))
  const quickWins = byRatio.filter((s) => isQuickWin(s.timeToBenefit))
  // Turns a priority order into a plan: the quick-win share first (in the order's preference,
  // then by gain per rupee), then everything else in order, all within the budget.
  const fill = (order: Site[], start: Site[] = []) => {
    const picked = [...start]
    let spent = picked.reduce((a, s) => a + cost(s), 0)
    let quick = picked.filter((s) => isQuickWin(s.timeToBenefit)).reduce((a, s) => a + cost(s), 0)
    const add = (s: Site) => {
      if (picked.includes(s) || (gain.get(s.id) ?? 0) <= 0 || spent + cost(s) > budgetInr) return
      picked.push(s)
      spent += cost(s)
      if (isQuickWin(s.timeToBenefit)) quick += cost(s)
    }
    for (const s of [...order.filter((x) => isQuickWin(x.timeToBenefit)), ...quickWins]) {
      if (quick >= quickWinTarget) break
      add(s)
    }
    for (const s of order) add(s)
    return picked
  }
  let n = 0
  const candidate = (round: number, source: Candidate['source'], label: string, sites: Site[]): Candidate => {
    const r = evaluate(sites)
    const invalidReason = r.costInr > budgetInr ? 'Over budget'
      : r.quickWinCostInr < quickWinTarget ? 'Below the quick-win share'
        : !r.ventilationOk ? 'Fails the ventilation check' : undefined
    return { id: `c${++n}`, round, source, label, changes: sites.map(changeOf), score: r.after.acs, costInr: r.costInr, valid: !invalidReason, invalidReason }
  }

  await sleep(500, signal)
  const greedy = candidate(0, 'greedy', 'Quick wins, then best gain per rupee', fill(byRatio))
  yield { type: 'baseline', candidate: greedy }

  const hot = new Set([...index.blocks].sort((a, b) => b.priority - a.priority).slice(0, 5).map((b) => b.id))
  const touchesHot = (s: Site) => Object.keys(s.effects.blocks).some((b) => hot.has(b))
    || Object.keys(s.effects.segments).some((id) => hot.has(index.segmentById.get(id)?.block ?? ''))
  const roundRobin = () => {
    const queues = (['shade', 'tree_row', 'depave', 'pocket_green', 'cool_roof'] as const).map((t) => byRatio.filter((s) => s.type === t))
    const out: Site[] = []
    while (queues.some((q) => q.length)) for (const q of queues) { const s = q.shift(); if (s) out.push(s) }
    return out
  }
  // Each proposal is a priority order; fill() turns it into a plan within the budget.
  const firstRound: [string, Site[]][] = [
    ['Shade at waiting points first', fill([...byRatio.filter((s) => s.type === 'shade'), ...byRatio])],
    ['Focus on the top hotspots', fill([...byRatio.filter(touchesHot), ...byRatio])],
    ['A mix of intervention types', fill(roundRobin())],
    ['Green links and depaving first', fill([...byRatio.filter((s) => s.type === 'pocket_green' || s.type === 'depave'), ...byRatio])],
  ]

  let best: Candidate | null = null
  let rounds = 0
  for (let round = 1; round <= MAX_ROUNDS; round++) {
    rounds = round
    yield { type: 'round', round }
    // Later rounds refine the best plan so far, baseline included (the proposer sees the baseline).
    const proposals: [string, Site[]][] = round === 1 ? firstRound : swaps(best && best.score >= greedy.score ? best : greedy)
    const previous = best?.score ?? -Infinity
    for (const [label, sites] of proposals) {
      await sleep(thinking(), signal)
      const c = candidate(round, 'gemini', label, sites)
      if (c.valid && (!best || c.score > best.score)) best = c
      yield { type: 'candidate', candidate: c }
    }
    if (round > 1 && (best?.score ?? 0) - previous <= STOP_THRESHOLD.repair) break
  }

  function swaps(from: Candidate): [string, Site[]][] {
    const current = from.changes.map((ch) => index.siteById.get(ch.siteId) as Site)
    const weakest = [...current].sort((a, b) => ratio(a) - ratio(b))
    const unused = byRatio.filter((s) => !current.includes(s))
    return [0, 1, 2, 3].map((i) => {
      const drop = weakest[i % Math.max(1, weakest.length)]
      const add = unused.filter((s) => s.type !== drop?.type)[i] ?? unused[i]
      const label = drop && add ? `Replace a ${typeLabel(drop)} with a ${typeLabel(add)}` : 'Use the remaining budget'
      return [label, fill(add ? [add, ...unused] : unused, current.filter((s) => s !== drop))]
    })
  }

  const rejected = affordable.filter((s) => !s.ventilation.ok)
    .map((s) => ({ s, g: evaluate([s]).after.acs - base }))
    .sort((a, b) => b.g - a.g).slice(0, 3)
    .map(({ s }) => ({ siteId: s.id, driver: s.ventilation.ok ? '' : s.ventilation.driver, reason: s.ventilation.ok ? '' : s.ventilation.reason }))

  const gemini = best ?? greedy
  const geminiBeatGreedy = gemini.score >= greedy.score
  const chosen = geminiBeatGreedy ? gemini : greedy
  const result = evaluate(chosen.changes.map((c) => index.siteById.get(c.siteId) as Site))
  await sleep(400, signal)
  yield {
    type: 'done',
    result: {
      best: chosen, geminiBeatGreedy, rejected, rounds,
      explanation: explainPlan(index, chosen, result, greedy, rejected.length, budgetInr, req.quickWinSharePct),
    },
  }
}

function typeLabel(s: Site) {
  return { tree_row: 'tree row', shade: 'shade structure', depave: 'depave site', pocket_green: 'pocket green', cool_roof: 'cool roof' }[s.type]
}

// ---------------- Protect: design search for options A, B and C ----------------

async function* protectSearch(index: AreaIndex, req: Extract<SearchRequest, { mode: 'protect' }>, signal: AbortSignal): AsyncGenerator<SearchEvent> {
  const parcel = index.parcelById.get(req.parcelId)
  if (!parcel) throw new Error(`Unknown parcel ${req.parcelId}`)
  const A = req.proposal
  const floorArea = (d: BuildingDesign) => (d.footprintPct / 100) * d.floors
  const windAxis = Math.round((index.area.engine.windFromDeg % 180) / ORIENTATION_STEP) * ORIENTATION_STEP
  const changeOf = (d: BuildingDesign): Change => ({
    kind: 'building', siteId: parcel.id, quantity: d.floors,
    params: { footprintPct: d.footprintPct, greenPct: d.greenPct, orientationDeg: d.orientationDeg },
  })
  const allowed = (d: BuildingDesign) => d.floors >= 1 && d.floors <= A.floors && d.footprintPct <= A.footprintPct
    && d.greenPct >= A.greenPct && d.footprintPct + d.greenPct <= 100 && d.orientationDeg % ORIENTATION_STEP === 0
  const designs = new Map<string, BuildingDesign>()
  let n = 0
  const candidate = (round: number, source: Candidate['source'], label: string, d: BuildingDesign): Candidate => {
    const r = rescoreMock(index, [changeOf(d)], index.area.unitCostDefaults)
    const c: Candidate = {
      id: `d${++n}`, round, source, label, changes: [changeOf(d)], score: r.risk?.change ?? 0, costInr: 0,
      floorAreaPct: Math.round((100 * floorArea(d)) / floorArea(A)), risk: r.risk, valid: allowed(d),
      invalidReason: allowed(d) ? undefined : 'Outside the allowed ranges',
    }
    designs.set(c.id, d)
    return c
  }
  const all: Candidate[] = []
  const bestWith = (minPct: number) => all.filter((c) => c.valid && (c.floorAreaPct ?? 0) >= minPct)
    .reduce<Candidate | null>((x, y) => (!x || y.score < x.score ? y : x), null)

  await sleep(500, signal)
  const proposal = candidate(0, 'proposal', 'As proposed', A)
  all.push(proposal)
  yield { type: 'baseline', candidate: proposal }

  const tweak = (d: BuildingDesign, patch: Partial<BuildingDesign>): BuildingDesign => {
    const next = { ...d, ...patch }
    next.floors = Math.max(1, Math.min(A.floors, Math.round(next.floors)))
    next.footprintPct = Math.max(10, Math.min(A.footprintPct, next.footprintPct))
    next.greenPct = Math.max(A.greenPct, Math.min(100 - next.footprintPct, next.greenPct))
    return next
  }
  const firstRound: [string, BuildingDesign][] = [
    ['Fewer floors', tweak(A, { floors: A.floors * 0.7 })],
    ['Smaller footprint, more green', tweak(A, { footprintPct: A.footprintPct - 15, greenPct: A.greenPct + 15 })],
    ['Long side turned to the wind', tweak(A, { orientationDeg: windAxis })],
    ['Lower and greener, turned to the wind', tweak(A, { floors: A.floors * 0.5, greenPct: A.greenPct + 10, orientationDeg: windAxis })],
  ]

  let rounds = 0
  for (let round = 1; round <= MAX_ROUNDS; round++) {
    rounds = round
    yield { type: 'round', round }
    const before = [bestWith(req.keepFloorAreaPct)?.score ?? Infinity, bestWith(req.minFloorAreaPct)?.score ?? Infinity]
    const proposals = round === 1 ? firstRound : refine()
    for (const [label, d] of proposals) {
      await sleep(thinking(), signal)
      const c = candidate(round, 'gemini', label, d)
      all.push(c)
      yield { type: 'candidate', candidate: c }
    }
    const after = [bestWith(req.keepFloorAreaPct)?.score ?? Infinity, bestWith(req.minFloorAreaPct)?.score ?? Infinity]
    if (round > 1 && before[0] - after[0] <= STOP_THRESHOLD.protect && before[1] - after[1] <= STOP_THRESHOLD.protect) break
  }

  function refine(): [string, BuildingDesign][] {
    const b = designs.get(bestWith(req.keepFloorAreaPct)?.id ?? proposal.id) as BuildingDesign
    const c = designs.get(bestWith(req.minFloorAreaPct)?.id ?? proposal.id) as BuildingDesign
    return [
      ['Option B: one floor lower', tweak(b, { floors: b.floors - 1 })],
      ['Option B: green on the wind side', tweak(b, { footprintPct: b.footprintPct - 5, greenPct: b.greenPct + 5, orientationDeg: windAxis })],
      ['Option C: two floors lower', tweak(c, { floors: c.floors - 2 })],
      ['Option C: smaller footprint', tweak(c, { footprintPct: c.footprintPct - 10, greenPct: c.greenPct + 10 })],
    ]
  }

  const optionB = bestWith(req.keepFloorAreaPct) ?? proposal
  const optionC = bestWith(req.minFloorAreaPct) ?? optionB
  const option = (key: DesignOption['key'], title: string, c: Candidate, tradeOff: string): DesignOption =>
    ({ key, title, candidate: c, design: designs.get(c.id) as BuildingDesign, tradeOff })
  const options: DesignOption[] = [
    option('A', 'Developer maximised', proposal, 'All the proposed floor area.'),
    option('B', 'Balanced', optionB, optionB.score >= proposal.score - NO_GAIN
      ? `Keeps ${optionB.floorAreaPct}% of the floor area, but no design at this share lowers the worst change.`
      : `Keeps ${optionB.floorAreaPct}% of the floor area.`),
    option('C', 'Climate optimised', optionC, `Keeps ${optionC.floorAreaPct}% of the floor area.`),
  ]
  await sleep(400, signal)
  yield {
    type: 'done',
    result: { best: optionB, options, rejected: [], rounds, explanation: explainDesigns(index, parcel, options, req.keepFloorAreaPct) },
  }
}
