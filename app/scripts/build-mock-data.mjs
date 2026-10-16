// Builds the mock API responses in public/mock/<area>/ from real OSM geometry.
//
// This is a stand-in for pipeline/ + engine/ so the UI can be built before the
// backend exists. Geometry, shadows and footpath shade are computed for real;
// index scores, unit costs and intervention effects are MOCK values that follow
// the shapes and formulas in docs/PLANNING.md but are not engine output.
//
// Usage: npm run mock:build

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import * as turf from '@turf/turf'
import * as SunCalc from 'suncalc'

const AREA_ID = 'deccan'
const SOURCE = 'scripts/source/deccan.osm.geojson'
const OUT = `public/mock/${AREA_ID}`

// Settings (mirror docs/PLANNING.md prototype settings where one exists).
const DEFAULT_HEIGHT_M = 9
const FOOTPATH_W_M = 2
const CHUNK_M = 10
const WAIT_RADIUS_M = 150
const SHADE_TIMES = ['13:00', '15:00', '16:00']
const REFERENCE_DATE = '2026-04-15'
const TREE_SPACING_M = 8
const CROWN = { r: 3, bottom: 3, top: 7 }
const SAIL = { w: 8, d: 6, h: 3 }
const DEEP_CANYON_HW = 1
const MOCK_WIND_FROM_DEG = 290 // mock prevailing wind; real value comes from Open-Meteo
const GRID = 0.0005

// Default unit costs: MOCK planner inputs for the demo, not market prices. Cited defaults arrive
// with WP8 (pipeline/config/unit_costs.yaml).
const MOCK_COST_SOURCE = 'Mock default; cited defaults arrive with WP8'
const UNIT_COSTS = {
  tree_row: { unit: 'tree', inr: 4500, source: MOCK_COST_SOURCE, sourceUrl: null },
  shade: { unit: 'm²', inr: 6500, source: MOCK_COST_SOURCE, sourceUrl: null },
  depave: { unit: 'm²', inr: 2200, source: MOCK_COST_SOURCE, sourceUrl: null },
  pocket_green: { unit: 'm²', inr: 1800, source: MOCK_COST_SOURCE, sourceUrl: null },
  cool_roof: { unit: 'm²', inr: 250, source: MOCK_COST_SOURCE, sourceUrl: null },
}
const TIME_TO_BENEFIT = { tree_row: 'years', shade: 'weeks', depave: 'season', pocket_green: 'years', cool_roof: 'weeks' }

const round = (n, d = 6) => Math.round(n * 10 ** d) / 10 ** d
const rc = (c) => [round(c[0]), round(c[1])]
const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v))
const r1 = (n) => Math.round(n * 10) / 10
// Deterministic pseudo-random in [0,1) from a string, so mock values are stable between builds.
const hash01 = (s) => {
  let h = 2166136261
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
  return ((h >>> 0) % 10000) / 10000
}
const write = (name, data) => writeFileSync(`${OUT}/${name}`, JSON.stringify(data))

// ---------- load ----------
const src = JSON.parse(readFileSync(SOURCE, 'utf8'))
const bbox = src.bbox
const center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
const buildings = []
const roads = []
const waits = []
const greens = []
for (const f of src.features) {
  const p = f.properties
  if (p.kind === 'building') {
    const ring = f.geometry.coordinates[0].map(rc)
    buildings.push({
      id: `bd${p.id}`, ring, h: p.height_m ?? DEFAULT_HEIGHT_M, source: p.height_m != null ? 'osm_height' : 'typology',
      area: turf.area(f), centroid: turf.centroid(f).geometry.coordinates,
    })
  } else if (p.kind === 'road') {
    const clipped = turf.bboxClip(f, bbox).geometry
    const parts = clipped.type === 'MultiLineString' ? clipped.coordinates : [clipped.coordinates]
    parts.filter((pt) => pt && pt.length > 1).forEach((pt, i) =>
      roads.push({ id: `rd${p.id}_${i}`, name: p.name, cls: p.class, width: p.width_m, line: turf.lineString(pt.map(rc)) }))
  } else if (p.kind === 'wait_point') {
    waits.push({ id: `wp${p.id}`, type: p.type, name: p.name, weight: p.weight, pos: rc(f.geometry.coordinates) })
  } else if (p.kind === 'green') {
    greens.push(f)
  }
}

// ---------- sun and shadows ----------
function sunAt(time) {
  const [h, m] = time.split(':').map(Number)
  const [y, mo, d] = REFERENCE_DATE.split('-').map(Number)
  const utc = new Date(Date.UTC(y, mo - 1, d, h, m) - 330 * 60000) // IST = UTC+5:30
  const p = SunCalc.getPosition(utc, center[1], center[0]) // suncalc v2: degrees, azimuth from north
  return { altDeg: p.altitude, shadowBearing: (p.azimuth + 180) % 360 }
}
const SUN = Object.fromEntries(SHADE_TIMES.map((t) => [t, sunAt(t)]))

function move(ring, metres, bearing) {
  return ring.map((c) => turf.destination(c, metres / 1000, bearing).geometry.coordinates)
}
// Shadow of a prism spanning z0..z1 metres: convex hull of the ring moved by both offsets.
function shadowOf(ring, z0, z1, sun) {
  if (sun.altDeg <= 1) return null
  const k = 1 / Math.tan((sun.altDeg * Math.PI) / 180)
  const pts = [...move(ring, z0 * k, sun.shadowBearing), ...move(ring, z1 * k, sun.shadowBearing)]
  const hull = turf.convex(turf.featureCollection(pts.map((c) => turf.point(c))))
  return hull ? hull.geometry.coordinates[0].map(rc) : null
}
function buildIndex(polys) {
  const index = new Map()
  for (const ring of polys) {
    const feature = turf.polygon([ring])
    const [w, s, e, n] = turf.bbox(feature)
    for (let x = Math.floor(w / GRID); x <= Math.floor(e / GRID); x++)
      for (let y = Math.floor(s / GRID); y <= Math.floor(n / GRID); y++) {
        const key = `${x},${y}`
        if (!index.has(key)) index.set(key, [])
        index.get(key).push({ bb: [w, s, e, n], feature })
      }
  }
  return index
}
function inIndex(index, pt) {
  const cell = index.get(`${Math.floor(pt[0] / GRID)},${Math.floor(pt[1] / GRID)}`)
  return !!cell?.some((c) => pt[0] >= c.bb[0] && pt[0] <= c.bb[2] && pt[1] >= c.bb[1] && pt[1] <= c.bb[3]
    && turf.booleanPointInPolygon(pt, c.feature))
}
const buildingShadows = Object.fromEntries(SHADE_TIMES.map((t) =>
  [t, buildings.map((b) => shadowOf(b.ring, 0, b.h, SUN[t])).filter(Boolean)]))
const shadowIndex = Object.fromEntries(SHADE_TIMES.map((t) => [t, buildIndex(buildingShadows[t])]))

// ---------- blocks (polygonize the road network) ----------
function buildBlocks() {
  const lines = [...roads.map((r) => r.line), turf.lineString(turf.bboxPolygon(bbox).geometry.coordinates[0])]
  const pieces = []
  for (let i = 0; i < lines.length; i++) {
    let parts = [lines[i]]
    for (let j = 0; j < lines.length; j++) {
      if (i === j || !turf.booleanIntersects(lines[i], lines[j])) continue
      parts = parts.flatMap((p) => {
        try { const s = turf.lineSplit(p, lines[j]).features; return s.length ? s : [p] } catch { return [p] }
      })
    }
    pieces.push(...parts)
  }
  const clean = []
  for (const sg of pieces) {
    const cs = []
    for (const c of sg.geometry.coordinates.map(rc)) {
      const last = cs[cs.length - 1]
      if (!last || last[0] !== c[0] || last[1] !== c[1]) cs.push(c)
    }
    if (cs.length >= 2 && turf.length(turf.lineString(cs), { units: 'meters' }) > 0.5) clean.push(turf.lineString(cs))
  }
  return turf.polygonize(turf.featureCollection(clean)).features
    .filter((f) => turf.area(f) > 300)
    .map((f, i) => ({ id: `bk${String(i + 1).padStart(3, '0')}`, feature: f, area: turf.area(f) }))
}
const blocks = buildBlocks()
const blockOf = (pt) => blocks.find((b) => turf.booleanPointInPolygon(pt, b.feature))?.id ?? null
for (const b of buildings) b.block = blockOf(b.centroid)

// ---------- footpath segments ----------
const COMPASS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west']
const compass = (deg) => COMPASS[Math.round(deg / 45) % 8]
const segments = []
const footpaths = [] // one per road side; candidate lines for tree rows
for (const road of roads) {
  for (const side of [-1, 1]) {
    let off
    try { off = turf.lineOffset(road.line, side * (road.width / 2 + FOOTPATH_W_M / 2), { units: 'meters' }) } catch { continue }
    const coords = road.line.geometry.coordinates
    const facing = (turf.bearing(coords[0], coords[coords.length - 1]) + (side > 0 ? 90 : -90) + 360) % 360
    const fp = { id: `${road.id}_${side > 0 ? 'r' : 'l'}`, road, line: off, segIds: [], sideName: compass(facing) }
    for (const chunk of turf.lineChunk(off, CHUNK_M, { units: 'meters' }).features) {
      const path = chunk.geometry.coordinates.map(rc)
      if (path.some((c) => !Number.isFinite(c[0]) || !Number.isFinite(c[1]))) continue
      const len = turf.length(chunk, { units: 'meters' })
      if (len < 1) continue
      const mid = rc(turf.along(chunk, len / 2, { units: 'meters' }).geometry.coordinates)
      const id = `sg${segments.length + 1}`
      segments.push({
        id, path, mid, len, footpath: fp.id, road: road.name, roadClass: road.cls,
        nearWait: waits.some((w) => turf.distance(mid, w.pos, { units: 'meters' }) < WAIT_RADIUS_M),
        shaded: SHADE_TIMES.map((t) => inIndex(shadowIndex[t], mid)),
        block: blockOf(turf.destination(mid, 0.004, (turf.bearing(path[0], path[path.length - 1]) + (side > 0 ? 90 : -90) + 360) % 360).geometry.coordinates),
      })
      fp.segIds.push(id)
    }
    if (fp.segIds.length) footpaths.push(fp)
  }
}

// ---------- mock block scores (formulas from docs/PLANNING.md, inputs mocked) ----------
const volumes = buildings.map((b) => b.area * b.h).sort((a, b) => a - b)
const V_REF = volumes[Math.floor(volumes.length * 0.95)]
function nearestGreenM(pt) {
  if (!greens.length) return 300
  return Math.min(...greens.map((g) => turf.pointToPolygonDistance(pt, g, { units: 'meters' })))
}
function heightToWidth(road) {
  const near = buildings.filter((b) => turf.pointToLineDistance(b.centroid, road.line, { units: 'meters' }) < road.width / 2 + 15)
  if (!near.length) return 0
  return near.reduce((a, b) => a + b.h, 0) / near.length / road.width
}
const roadHW = new Map(roads.map((r) => [r.id, heightToWidth(r)]))

const blockScores = new Map()
for (const b of blocks) {
  const inside = buildings.filter((x) => x.block === b.id)
  const coverage = Math.min(1, inside.reduce((a, x) => a + x.area, 0) / b.area)
  const footprints = inside.map((x) => x.area).sort((a, c) => a - c)
  const medianFootprint = footprints.length ? footprints[Math.floor(footprints.length / 2)] : 0
  const c = turf.centroid(b.feature).geometry.coordinates
  const dGreen = Math.max(0, nearestGreenM(c))
  const Gc = clamp(5 + 25 * hash01(`${b.id}g`) * (1 - coverage) + (dGreen < 50 ? 20 : 0))
  const Is = clamp(35 + 60 * coverage)
  const Tm = clamp((100 * inside.reduce((a, x) => a + x.area * x.h, 0)) / inside.length / V_REF || 0)
  const roofAlbedo = 0.15 + 0.2 * hash01(`${b.id}a`)
  const Ra = clamp((100 * (0.7 - roofAlbedo)) / 0.6)
  const hei = 0.35 * Is + 0.3 * (100 - Gc) + 0.2 * Tm + 0.15 * Ra
  const Llink = Math.max(0, 100 - dGreen / 3)
  const gcs = 0.5 * clamp(Gc * 1.2) + 0.5 * Llink
  const edge = turf.polygonToLine(b.feature)
  const bearing = turf.bearing(turf.point(edge.geometry.coordinates[0]), turf.point(edge.geometry.coordinates[1]))
  const Wa = 100 * Math.abs(Math.cos(((bearing - MOCK_WIND_FROM_DEG) * Math.PI) / 180))
  const Co = clamp(100 - coverage * 120)
  const adjRoads = roads.filter((r) => turf.booleanIntersects(r.line, turf.buffer(b.feature, 10, { units: 'meters' })))
  const hw = adjRoads.length ? Math.max(...adjRoads.map((r) => roadHW.get(r.id))) : 0
  const Ob = 100 * (1 - Math.min(1, hw / 2.5))
  const Pg = Math.max(0, 100 - dGreen / 10)
  const vci = 0.3 * Wa + 0.25 * Co + 0.25 * Ob + 0.2 * Pg
  const segs = segments.filter((s) => s.block === b.id)
  const segLen = segs.reduce((a, s) => a + s.len, 0)
  const pss = segLen ? (100 * segs.reduce((a, s) => a + s.len * (s.shaded.filter(Boolean).length / SHADE_TIMES.length), 0)) / segLen : 0
  const waitW = waits.filter((w) => turf.pointToPolygonDistance(w.pos, b.feature, { units: 'meters' }) < WAIT_RADIUS_M)
    .reduce((a, w) => a + w.weight, 0)
  const E = 1 + Math.min(2, waitW / 3)
  // MOCK built-form rule: this area is mid-rise, so the real rule in docs/PLANNING.md finds no blocks.
  const denseLowRise = coverage >= 0.28 && medianFootprint <= 220 && inside.length >= 10
  const V = denseLowRise ? 1.25 : 1
  const priority = hei * (1 - pss / 100) * E * V
  const drivers = []
  if (Is >= 65) drivers.push('IMPERVIOUS_HIGH')
  if (pss < 25) drivers.push('LOW_SHADE')
  if (waitW >= 3) drivers.push('WAIT_POINTS')
  if (denseLowRise) drivers.push('DENSE_LOW_RISE')
  if (Gc < 15) drivers.push('LOW_GREEN')
  blockScores.set(b.id, {
    coverage, builtForm: denseLowRise ? 'dense_low_rise' : 'other', waitWeight: waitW, E, V,
    scores: { vci: r1(vci), hei: r1(hei), gcs: r1(gcs), pss: r1(pss) }, priority: r1(priority), drivers,
    hw: r1(hw), centroid: rc(c),
  })
}
const prSorted = [...blockScores.values()].map((s) => s.priority).sort((a, b) => a - b)
const tHigh = prSorted[Math.floor(prSorted.length * 0.67)]
const tMed = prSorted[Math.floor(prSorted.length * 0.34)]
const priorityClass = (p) => (p >= tHigh ? 'high' : p >= tMed ? 'medium' : 'low')

// ---------- candidate sites and their mock effects ----------
const segById = new Map(segments.map((s) => [s.id, s]))
const segIndexNear = (geom, metres) => {
  const zone = turf.buffer(geom, metres, { units: 'meters' })
  const [w, s, e, n] = turf.bbox(zone)
  return segments.filter((sg) => sg.mid[0] >= w && sg.mid[0] <= e && sg.mid[1] >= s && sg.mid[1] <= n)
}
// Which nearby segments a set of new shade-casting rings shades, per time.
function shadeEffect(rings, z0, z1, searchGeom, radiusM = 40) {
  const candidates = segIndexNear(searchGeom, radiusM)
  const out = {}
  SHADE_TIMES.forEach((t, ti) => {
    const idx = buildIndex(rings.map((r) => shadowOf(r, z0, z1, SUN[t])).filter(Boolean))
    for (const sg of candidates) if (!sg.shaded[ti] && inIndex(idx, sg.mid)) (out[sg.id] ??= [false, false, false])[ti] = true
  })
  return out
}
// Axis-aligned rectangle ring of w × d metres centred on a point.
function rectRing(center, w, d) {
  const corners = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]]
    .map(([dx, dy]) => rc(turf.destination(turf.destination(center, dx / 1000, 90), dy / 1000, 0).geometry.coordinates))
  return [...corners, corners[0]]
}
const sites = []
const addSite = (s) => sites.push({ ...s, timeToBenefit: TIME_TO_BENEFIT[s.type] })

// Street tree rows: one candidate per footpath on roads wide enough for a planting strip.
for (const fp of footpaths) {
  const len = turf.length(fp.line, { units: 'meters' })
  if (len < 40 || !['primary', 'secondary', 'tertiary', 'residential', 'unclassified'].includes(fp.road.cls)) continue
  const trees = []
  for (let d = TREE_SPACING_M / 2; d < len; d += TREE_SPACING_M) trees.push(rc(turf.along(fp.line, d, { units: 'meters' }).geometry.coordinates))
  const rings = trees.map((c) => turf.circle(c, CROWN.r, { units: 'meters', steps: 8 }).geometry.coordinates[0])
  const hw = roadHW.get(fp.road.id)
  const deep = hw >= DEEP_CANYON_HW
  const blocksTouched = [...new Set(fp.segIds.map((id) => segById.get(id).block).filter(Boolean))]
  const dGc = Math.min(8, (trees.length * 28) / 1000)
  const mainBlock = blocksTouched.sort((x, y) => fp.segIds.filter((id) => segById.get(id).block === y).length - fp.segIds.filter((id) => segById.get(id).block === x).length)[0]
  addSite({
    id: `st_${fp.id}`, type: 'tree_row',
    name: `Tree row, ${fp.road.name ?? `unnamed ${fp.road.cls} road`}, ${fp.sideName} side${mainBlock ? `, block ${mainBlock.slice(2)}` : ''}`,
    geometry: { type: 'LineString', coordinates: fp.line.geometry.coordinates.map(rc) }, points: trees,
    quantity: trees.length, hw: r1(hw),
    ventilation: deep ? { ok: false, driver: 'CANOPY_OBSTRUCTION', reason: `Deep, narrow street (height-to-width ${r1(hw)}). Dense canopy would block the breeze and trap heat at night.` } : { ok: true },
    effects: {
      segments: shadeEffect(rings, CROWN.bottom, CROWN.top, fp.line),
      // Deep streets never enter a plan (site rule, docs/PLANNING.md), so tree rows don't change VCI.
      blocks: Object.fromEntries(blocksTouched.map((b) => [b, { hei: r1(-0.3 * dGc), gcs: r1(0.5 * dGc), vci: 0 }])),
    },
    drivers: deep ? ['CANOPY_OBSTRUCTION'] : ['SHADE_GAIN', 'GREEN_LINK'],
  })
}
// Shade structures on the footpath nearest each waiting point (its street entrance).
for (const w of waits) {
  const nearest = segments.reduce((best, sg) => {
    const d = turf.distance(w.pos, sg.mid, { units: 'meters' })
    return d < best.d ? { d, sg } : best
  }, { d: Infinity, sg: null })
  if (!nearest.sg || nearest.d > 60) continue
  const ring = rectRing(nearest.sg.mid, SAIL.w, SAIL.d)
  addSite({
    id: `ss_${w.id}`, type: 'shade', name: `Shade structure, ${w.name ?? w.type}`,
    geometry: { type: 'Polygon', coordinates: [ring] }, quantity: SAIL.w * SAIL.d, waitPoint: w.id,
    ventilation: { ok: true },
    // The segment under the sail counts as shaded at every time: people stand beneath it.
    effects: { segments: { ...shadeEffect([ring], SAIL.h, SAIL.h, turf.polygon([ring])), [nearest.sg.id]: [true, true, true] }, blocks: {} },
    drivers: ['SHADE_GAIN', 'WAIT_POINT_COVERED'],
  })
}
// Depave and plant: school and college grounds (mock yard around the waiting point).
for (const w of waits.filter((x) => ['school', 'college'].includes(x.type))) {
  const yard = turf.bboxPolygon(turf.bbox(turf.buffer(turf.point(w.pos), 14, { units: 'meters' })))
  const block = blockOf(w.pos)
  const area = Math.round(turf.area(yard))
  const share = block ? (100 * area) / blocks.find((b) => b.id === block).area : 0
  addSite({
    id: `dp_${w.id}`, type: 'depave', name: `Depave and plant, ${w.name ?? 'school yard'}`,
    geometry: { type: 'Polygon', coordinates: [yard.geometry.coordinates[0].map(rc)] }, quantity: area, waitPoint: w.id,
    ventilation: { ok: true },
    effects: { segments: {}, blocks: block ? { [block]: { hei: r1(-0.35 * share - 0.3 * share * 0.8), gcs: r1(0.5 * share * 0.8), vci: 0 } } : {} },
    drivers: ['IMPERVIOUS_LOSS'],
  })
}
// Pocket green: low-coverage blocks, placed at the block centre.
const lowCoverage = blocks.filter((b) => blockScores.get(b.id).coverage < 0.2 && b.area < 25000)
  .sort((a, b) => blockScores.get(a.id).coverage - blockScores.get(b.id).coverage).slice(0, 5)
for (const b of lowCoverage) {
  const c = blockScores.get(b.id).centroid
  const plot = turf.bboxPolygon(turf.bbox(turf.buffer(turf.point(c), 12, { units: 'meters' })))
  const neighbours = blocks.filter((o) => o.id !== b.id && turf.distance(c, blockScores.get(o.id).centroid, { units: 'meters' }) < 200)
  addSite({
    id: `pg_${b.id}`, type: 'pocket_green', name: `Pocket green, plot in block ${b.id.slice(2)}`,
    geometry: { type: 'Polygon', coordinates: [plot.geometry.coordinates[0].map(rc)] }, quantity: Math.round(turf.area(plot)),
    ventilation: { ok: true },
    effects: {
      segments: {},
      blocks: Object.fromEntries([[b.id, { hei: -3, gcs: 9, vci: 0 }], ...neighbours.map((o) => [o.id, { hei: -0.5, gcs: 3, vci: 0 }])]),
    },
    drivers: ['GREEN_LINK'],
  })
}
// Cool roofs: dense low-rise blocks.
for (const b of blocks.filter((x) => blockScores.get(x.id).builtForm === 'dense_low_rise')) {
  const roofs = buildings.filter((x) => x.block === b.id)
  addSite({
    id: `cr_${b.id}`, type: 'cool_roof', name: `Cool roofs, ${roofs.length} buildings in block ${b.id.slice(2)}`,
    geometry: { type: 'MultiPolygon', coordinates: roofs.map((x) => [x.ring]) }, quantity: Math.round(roofs.reduce((a, x) => a + x.area, 0)),
    ventilation: { ok: true },
    effects: { segments: {}, blocks: { [b.id]: { hei: -8, gcs: 0, vci: 0 } } },
    drivers: ['ALBEDO_GAIN'],
  })
}

// ---------- Protect: candidate vacant parcels ----------
// A parcel is a plot inside a low-coverage block. Shade effects of a proposed building are
// precomputed for a grid of footprint shares and heights, so the mock can look them up.
const PARCEL = { w: 36, d: 28 }
const FOOTPRINT_LEVELS = [25, 40, 55, 70]
const HEIGHT_LEVELS = [6, 12, 18, 30, 45, 60]
const parcels = []
const parcelBlocks = blocks.filter((b) => blockScores.get(b.id).coverage < 0.25 && b.area > 2500)
  .sort((a, b) => blockScores.get(a.id).coverage - blockScores.get(b.id).coverage)
for (const b of parcelBlocks) {
  if (parcels.length >= 8) break
  const c = rc(turf.pointOnFeature(b.feature).geometry.coordinates)
  const plot = rectRing(c, PARCEL.w, PARCEL.d)
  if (!turf.booleanWithin(turf.polygon([plot]), b.feature)) continue
  const road = roads.reduce((best, r) => {
    const d = turf.pointToLineDistance(c, r.line, { units: 'meters' })
    return d < best.d ? { d, r } : best
  }, { d: Infinity, r: null }).r
  const coords = road.line.geometry.coordinates
  const streetBearing = (turf.bearing(coords[0], coords[coords.length - 1]) + 360) % 180
  const near = buildings.filter((x) => turf.distance(c, x.centroid, { units: 'meters' }) < 80)
  const shade = {}
  for (const fp of FOOTPRINT_LEVELS) {
    const k = Math.sqrt(fp / 100)
    const ring = rectRing(c, PARCEL.w * k, PARCEL.d * k)
    for (const h of HEIGHT_LEVELS) shade[`${fp}_${h}`] = shadeEffect([ring], 0, h, turf.polygon([ring]), 100)
  }
  parcels.push({
    id: `pc${String(parcels.length + 1).padStart(2, '0')}`, blockId: b.id, plot, center: c,
    name: `Vacant plot on ${road.name ?? `an unnamed ${road.cls} road`}`, areaM2: Math.round(turf.area(turf.polygon([plot]))),
    roadName: road.name, roadWidthM: road.width, streetBearingDeg: Math.round(streetBearing),
    neighbourHeightM: r1(near.length ? near.reduce((a, x) => a + x.h, 0) / near.length : DEFAULT_HEIGHT_M),
    nearbyBlocks: blocks.filter((o) => o.id !== b.id && turf.distance(c, blockScores.get(o.id).centroid, { units: 'meters' }) < 200).map((o) => o.id),
    shade,
  })
}

// ---------- area summary ----------
function areaScores() {
  let w = 0
  const acc = { vci: 0, hei: 0, gcs: 0, pss: 0, acs: 0 }
  for (const s of blockScores.values()) {
    const wb = s.E * s.V
    const c = 0.45 * (100 - s.scores.hei) + 0.35 * s.scores.pss + 0.2 * s.scores.gcs
    w += wb
    for (const k of ['vci', 'hei', 'gcs', 'pss']) acc[k] += wb * s.scores[k]
    acc.acs += wb * c
  }
  return Object.fromEntries(Object.entries(acc).map(([k, v]) => [k, r1(v / w)]))
}

// ACS with one site's mock effects applied, using the formula from docs/PLANNING.md. The mock
// stand-in for the engine's single-site result (contract Site.singleSite).
const segsByBlock = new Map()
for (const sg of segments) if (sg.block) (segsByBlock.get(sg.block) ?? segsByBlock.set(sg.block, []).get(sg.block)).push(sg)
function acsWith(effects) {
  let w = 0
  let acc = 0
  for (const [id, s] of blockScores) {
    const d = effects.blocks[id]
    const segs = segsByBlock.get(id) ?? []
    let pss = s.scores.pss
    if (segs.some((sg) => effects.segments[sg.id])) {
      const len = segs.reduce((a, sg) => a + sg.len, 0)
      const share = (sg) => {
        const add = effects.segments[sg.id]
        return sg.shaded.filter((v, i) => v || (add && add[i])).length / SHADE_TIMES.length
      }
      pss = len ? (100 * segs.reduce((a, sg) => a + sg.len * share(sg), 0)) / len : pss
    }
    const hei = clamp(s.scores.hei + (d?.hei ?? 0))
    const gcs = clamp(s.scores.gcs + (d?.gcs ?? 0))
    const wb = s.E * s.V
    w += wb
    acc += wb * (0.45 * (100 - hei) + 0.35 * pss + 0.2 * gcs)
  }
  return acc / w
}
const BASE_ACS = acsWith({ segments: {}, blocks: {} })

// ---------- write ----------
mkdirSync(OUT, { recursive: true })
const fc = (features) => ({ type: 'FeatureCollection', features })
const feat = (geometry, properties) => ({ type: 'Feature', geometry, properties })

const heightCount = (src) => buildings.filter((b) => b.source === src).length
write('area.json', {
  id: AREA_ID, name: 'Deccan Gymkhana – Fergusson College', city: 'Pune', bundleVersion: 'mock-1', bbox, center: rc(center),
  referenceDate: REFERENCE_DATE, shadeTimes: SHADE_TIMES, baseline: areaScores(),
  counts: { blocks: blocks.length, buildings: buildings.length, segments: segments.length, waitPoints: waits.length, sites: sites.length, parcels: parcels.length },
  dataGaps: {
    buildingsByHeightSource: { osm_height: heightCount('osm_height'), osm_levels: 0, open_buildings: 0, typology: heightCount('typology') },
    derivedFootpathSegments: segments.length,
    skippedSteps: ['earth_engine'],
  },
  unitCostDefaults: UNIT_COSTS,
  engine: { windFromDeg: MOCK_WIND_FROM_DEG, metresPerFloor: 3 },
  mock: true,
  attribution: 'Geometry © OpenStreetMap contributors (ODbL). Scores, costs and effects are mock values.',
})
write('blocks.json', fc(blocks.map((b) => {
  const s = blockScores.get(b.id)
  return feat(b.feature.geometry, {
    id: b.id, areaM2: Math.round(b.area), scores: s.scores, priority: s.priority, priorityClass: priorityClass(s.priority),
    builtForm: s.builtForm, waitWeight: s.waitWeight, drivers: s.drivers, centroid: s.centroid,
  })
})))
write('buildings.json', fc(buildings.map((b) => feat({ type: 'Polygon', coordinates: [b.ring] }, { id: b.id, heightM: b.h, heightSource: b.source }))))
write('segments.json', fc(segments.map((s) => feat({ type: 'LineString', coordinates: s.path }, {
  id: s.id, road: s.road, roadClass: s.roadClass, lengthM: r1(s.len), block: s.block, nearWait: s.nearWait, shaded: s.shaded,
}))))
write('wait-points.json', fc(waits.map((w) => feat({ type: 'Point', coordinates: w.pos }, { id: w.id, type: w.type, name: w.name, weight: w.weight }))))
for (const t of SHADE_TIMES) {
  write(`shadows-${t.replace(':', '')}.json`, fc(buildingShadows[t].map((r) => feat({ type: 'Polygon', coordinates: [r] }, {}))))
}
// Contract shapes (contract/ecozone_contract): sites carry the single-site result; parcels drop the
// mock shade lookup. Optional fields are explicit nulls, as the API serializes them.
write('sites.json', sites.map((s) => ({
  id: s.id, type: s.type, name: s.name, geometry: s.geometry, points: s.points ?? null, quantity: s.quantity,
  timeToBenefit: s.timeToBenefit, waitPoint: s.waitPoint ?? null, hw: s.hw ?? null,
  singleSite: {
    acsGain: r1(acsWith(s.effects) - BASE_ACS),
    drivers: s.drivers,
    ventilation: s.ventilation.ok ? { ok: true, driver: null, reason: null } : s.ventilation,
  },
})))
write('parcels.json', fc(parcels.map(({ plot, shade: _shade, nearbyBlocks: _nearby, ...p }) => feat({ type: 'Polygon', coordinates: [plot] }, p))))
// Mock-only engine data for the app's mock rescore (UI_RULES.md §8). Not part of the contract;
// it goes away when the app runs on the real API.
write('_mock-engine.json', {
  engine: { vRefM3: Math.round(V_REF), footprintLevels: FOOTPRINT_LEVELS, heightLevelsM: HEIGHT_LEVELS },
  sites: Object.fromEntries(sites.map((s) => [s.id, s.effects])),
  parcels: Object.fromEntries(parcels.map((p) => [p.id, { nearbyBlocks: p.nearbyBlocks, shade: p.shade }])),
})
write('hotspots.json', [...blockScores.entries()].sort((a, b) => b[1].priority - a[1].priority).slice(0, 10)
  .map(([id, s], i) => ({ rank: i + 1, blockId: id, priority: s.priority, priorityClass: priorityClass(s.priority), scores: s.scores, drivers: s.drivers, centroid: s.centroid })))

const byType = sites.reduce((a, s) => ({ ...a, [s.type]: (a[s.type] ?? 0) + 1 }), {})
console.log(`wrote ${OUT}: ${blocks.length} blocks, ${segments.length} segments, ${sites.length} sites, ${parcels.length} parcels`, byType, 'baseline', areaScores())
