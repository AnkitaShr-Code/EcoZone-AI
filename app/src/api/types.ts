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
  /** Engine constants the UI shows or passes back (never used to compute scores in the UI). */
  engine: { windFromDeg: number; vRefM3: number; metresPerFloor: number; footprintLevels: number[]; heightLevelsM: number[] }
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
  centroid: [number, number]
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

/** A vacant plot that Protect can test a proposed building on. */
export interface ParcelProps {
  id: string
  blockId: string
  name: string
  areaM2: number
  center: [number, number]
  roadName: string | null
  roadWidthM: number
  streetBearingDeg: number
  neighbourHeightM: number
  nearbyBlocks: string[]
  /** Engine lookup: footpath shade added by a building, keyed "<footprint %>_<height m>". */
  shade: Record<string, Record<string, ShadeByTime>>
}

/** Map layers served by GET /api/areas/{area}/layers/{name}. */
export interface LayerData {
  blocks: FeatureCollection<Polygon, BlockProps>
  segments: FeatureCollection<LineString, SegmentProps>
  buildings: FeatureCollection<Polygon, BuildingProps>
  waitPoints: FeatureCollection<Point, WaitPointProps>
  parcels: FeatureCollection<Polygon, ParcelProps>
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

/** A proposed building envelope (Protect). Floor area proxy = footprint % × floors. */
export interface BuildingDesign {
  floors: number
  footprintPct: number
  greenPct: number
  orientationDeg: number
}

export type RiskLabel = 'LOW' | 'MODERATE' | 'HIGH'

/** Worst change on a parcel's block: the largest of VCI drop, HEI rise, GCS drop, PSS drop. */
export interface RiskInfo {
  label: RiskLabel
  index: IndexKey
  change: number
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
  /** Cost of interventions that help within weeks or one season (docs/PLANNING.md, quick-win share). */
  quickWinCostInr: number
  drivers: string[]
  /** Existing blocks whose cooling score falls. */
  blocksWorse: number
  /** Protect: the worst risk across proposed buildings, and per parcel. */
  risk?: RiskInfo
  parcelRisk?: Record<string, RiskInfo>
}

export interface RejectedOption {
  siteId: string
  driver: string
  reason: string
}

/** One option scored by the engine during a search. */
export interface Candidate {
  id: string
  round: number
  source: 'gemini' | 'greedy' | 'proposal'
  label: string
  changes: Change[]
  /** Repair: area cooling score after. Protect: worst change (lower is better). */
  score: number
  costInr: number
  floorAreaPct?: number
  /** Protect: the engine's risk label for this design. */
  risk?: RiskInfo
  valid: boolean
  invalidReason?: string
}

export type SearchRequest =
  | { mode: 'repair'; budgetInr: number; unitCosts: UnitCosts; quickWinSharePct: number }
  | { mode: 'protect'; parcelId: string; proposal: BuildingDesign; keepFloorAreaPct: number; minFloorAreaPct: number }

export interface DesignOption {
  key: 'A' | 'B' | 'C'
  title: string
  candidate: Candidate
  design: BuildingDesign
  tradeOff: string
}

export interface SearchResult {
  best: Candidate
  /** Repair: whether Gemini's best beat the greedy baseline (if not, best is the greedy plan). */
  geminiBeatGreedy?: boolean
  /** Protect: options A, B and C. */
  options?: DesignOption[]
  rejected: RejectedOption[]
  rounds: number
  explanation: Explanation
}

/** Streamed over SSE from POST /api/agent/runs (DESIGN.md C3). */
export type SearchEvent =
  | { type: 'baseline'; candidate: Candidate }
  | { type: 'round'; round: number }
  | { type: 'candidate'; candidate: Candidate }
  | { type: 'done'; result: SearchResult }

/** An explanation written by the agent from engine values; every number appears in a tool result. */
export interface Explanation {
  paragraphs: string[]
  drivers: string[]
  /** 'template' when the output guard rejected the model twice and fell back. */
  source: 'gemini' | 'template'
}
