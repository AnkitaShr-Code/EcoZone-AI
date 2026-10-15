// API contract. Mirrors the Pydantic schemas planned in docs/DESIGN.md (C3).
// Written once here; every adapter (mock, http) returns exactly these shapes.

import type { FeatureCollection, LineString, MultiPolygon, Point, Polygon } from 'geojson'

export type Mode = 'repair' | 'protect'
export type ShadeTime = '13:00' | '15:00' | '16:00'
export type InterventionType = 'tree_row' | 'shade' | 'depave' | 'pocket_green' | 'cool_roof'
export type PriorityClass = 'high' | 'medium' | 'low'
export type IndexKey = 'vci' | 'hei' | 'gcs' | 'pss'
export type TimeToBenefit = 'weeks' | 'season' | 'years'

/** Shade state per reference time, in the order of AreaSummary.shadeTimes. */
export type ShadeByTime = [boolean, boolean, boolean]

export type Scores = Record<IndexKey, number>
export interface AreaScores extends Scores {
  acs: number
}

export interface UnitCost {
  unit: string
  inr: number
}
export type UnitCosts = Record<InterventionType, UnitCost>

export interface AreaSummary {
  id: string
  name: string
  city: string
  bbox: [number, number, number, number]
  center: [number, number]
  referenceDate: string
  shadeTimes: ShadeTime[]
  baseline: AreaScores
  counts: { blocks: number; buildings: number; segments: number; waitPoints: number; sites: number }
  dataGaps: { buildingsDefaultHeight: number; defaultHeightM: number }
  unitCostDefaults: UnitCosts
  mock: boolean
  attribution: string
}

export interface BlockProps {
  id: string
  areaM2: number
  scores: Scores
  priority: number
  priorityClass: PriorityClass
  builtForm: 'dense_low_rise' | 'other'
  waitWeight: number
  drivers: string[]
}

export interface SegmentProps {
  id: string
  road: string | null
  roadClass: string
  lengthM: number
  block: string | null
  nearWait: boolean
  shaded: ShadeByTime
}

export interface BuildingProps {
  id: string
  heightM: number
  heightSource: 'osm' | 'open_buildings' | 'default'
}

export interface WaitPointProps {
  id: string
  type: string
  name: string | null
  weight: number
}

export type ShadowProps = Record<string, never>

/** Map layers served by GET /api/areas/{area}/layers/{name}. */
export interface LayerData {
  blocks: FeatureCollection<Polygon, BlockProps>
  segments: FeatureCollection<LineString, SegmentProps>
  buildings: FeatureCollection<Polygon, BuildingProps>
  waitPoints: FeatureCollection<Point, WaitPointProps>
  shadows: Record<ShadeTime, FeatureCollection<Polygon, ShadowProps>>
}
export type LayerName = keyof LayerData

export interface Hotspot {
  rank: number
  blockId: string
  priority: number
  priorityClass: PriorityClass
  scores: Scores
  drivers: string[]
  centroid: [number, number]
}

export interface IndexDelta {
  hei: number
  gcs: number
  vci: number
}

export interface Site {
  id: string
  type: InterventionType
  name: string
  geometry: LineString | Polygon | MultiPolygon
  /** Tree positions for tree rows. */
  points?: [number, number][]
  quantity: number
  unitCost: UnitCost
  timeToBenefit: TimeToBenefit
  waitPoint?: string
  hw?: number
  ventilation: { ok: true } | { ok: false; driver: string; reason: string }
  effects: { segments: Record<string, ShadeByTime>; blocks: Record<string, IndexDelta> }
  drivers: string[]
}

/** One change to an area: an intervention (Repair) or a building (Protect). */
export interface Change {
  kind: InterventionType | 'building'
  siteId: string
  quantity: number
  params?: Record<string, number | string>
}

export interface BlockResult {
  id: string
  before: Scores
  after: Scores
}

/** Result of POST /api/areas/{area}/rescore. */
export interface AreaResult {
  before: AreaScores
  after: AreaScores
  blocks: BlockResult[]
  /** Segments whose shade changed, with their new shade state. */
  segments: Record<string, ShadeByTime>
  ventilationOk: boolean
  worstVciDrop: number
  waitPointsCovered: number
  costInr: number
  drivers: string[]
}
