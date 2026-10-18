// Every map data layer, defined once (UI_RULES.md §4). The layers control, the
// legend and the deck.gl layer list are all generated from this array.
// Adding a layer = adding one entry here (plus its render function in ./layers).

import type { Layer } from '@deck.gl/core'
import type { AreaResult, Change, LayerData, LayerName, Mode, RejectedOption, ShadeTime, Site } from '@/api/types'
import type { ColorToken } from '@/lib/colors'
import type { MapView } from '@/state/scenarioStore'
import type { Selection, SelectionKind } from '@/state/uiStore'
import { renderBuildings } from './layers/buildings'
import { renderChanges } from './layers/changes'
import { renderFootpathShade } from './layers/footpathShade'
import { renderParcels } from './layers/parcels'
import { renderPriority } from './layers/priority'
import { renderRejected } from './layers/rejected'
import { renderShadows } from './layers/shadows'
import { renderWaitPoints } from './layers/waitPoints'

export type LayerGroup = 'analysis' | 'plan' | 'context'

export const LAYER_GROUPS: { id: LayerGroup; label: string }[] = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'plan', label: 'Plan' },
  { id: 'context', label: 'Context' },
]

export interface LegendEntry {
  label: string
  color: ColorToken
  shape: 'fill' | 'line' | 'dot'
  /** Shown only when the working scenario contains a change of this kind. */
  changeKind?: Change['kind']
}

/** The working scenario as the map sees it. */
export interface ScenarioContext {
  view: MapView
  changes: Change[]
  rejected: RejectedOption[]
  result: AreaResult | undefined
}

export interface LayerContext {
  mode: Mode
  data: Partial<LayerData>
  sites: Site[] | undefined
  shadeTime: ShadeTime
  /** Position of shadeTime in AreaSummary.shadeTimes; indexes ShadeByTime arrays. */
  shadeIndex: number
  selection: Selection | null
  scenario: ScenarioContext
  metresPerFloor: number
}

export interface LayerDef {
  id: string
  label: string
  description: string
  group: LayerGroup
  /** Modes the layer exists in; omitted = both. */
  modes?: Mode[]
  defaultOn: Record<Mode, boolean>
  /** Layer data this layer needs; loaded only while the layer is visible. */
  needs: LayerName[]
  needsSites?: boolean
  /** Draws only the working scenario; hidden from the legend until there is one. */
  scenarioOnly?: boolean
  /** Shows the shade-time control while visible. */
  usesShadeTime?: boolean
  /** Clicking a feature selects it as this kind. */
  selects?: SelectionKind
  legend: LegendEntry[] | Record<Mode, LegendEntry[]>
  render: (ctx: LayerContext) => Layer[]
}

export const LAYERS = [
  {
    id: 'priority',
    label: 'Priority',
    description: 'Where heat, missing shade and waiting people overlap.',
    group: 'analysis',
    modes: ['repair'],
    defaultOn: { repair: true, protect: false },
    needs: ['blocks'],
    selects: 'block',
    legend: [
      { label: 'High priority', color: 'priority-high', shape: 'fill' },
      { label: 'Medium priority', color: 'priority-medium', shape: 'fill' },
      { label: 'Low priority', color: 'priority-low', shape: 'fill' },
    ],
    render: renderPriority,
  },
  {
    id: 'footpathShade',
    label: 'Footpath shade',
    description: 'Footpath in sun or shade at the selected time, today or with the plan.',
    group: 'analysis',
    defaultOn: { repair: true, protect: true },
    needs: ['segments'],
    usesShadeTime: true,
    selects: 'segment',
    legend: [
      { label: 'Footpath in sun', color: 'data-sun', shape: 'line' },
      { label: 'Footpath in shade', color: 'data-shade', shape: 'line' },
    ],
    render: renderFootpathShade,
  },
  {
    id: 'shadows',
    label: 'Shadows',
    description: 'Building shadows today at the selected time.',
    group: 'analysis',
    defaultOn: { repair: true, protect: false },
    needs: ['shadows'],
    usesShadeTime: true,
    legend: [{ label: 'Building shadow', color: 'map-shadow', shape: 'fill' }],
    render: renderShadows,
  },
  {
    id: 'changes',
    label: 'Proposed changes',
    description: 'The plan or proposal you are reviewing.',
    group: 'plan',
    defaultOn: { repair: true, protect: true },
    needs: ['parcels'],
    needsSites: true,
    scenarioOnly: true,
    selects: 'site',
    legend: {
      repair: [
        { label: 'Street tree row', color: 'iv-tree', shape: 'dot', changeKind: 'tree_row' },
        { label: 'Shade structure', color: 'iv-shade', shape: 'fill', changeKind: 'shade' },
        { label: 'Depave and plant', color: 'iv-depave', shape: 'fill', changeKind: 'depave' },
        { label: 'Pocket green', color: 'iv-green', shape: 'fill', changeKind: 'pocket_green' },
        { label: 'Cool roof', color: 'iv-roof', shape: 'fill', changeKind: 'cool_roof' },
      ],
      protect: [{ label: 'Proposed building', color: 'map-proposal', shape: 'fill' }],
    },
    render: renderChanges,
  },
  {
    id: 'rejected',
    label: 'Rejected options',
    description: 'Options the engine rejected, with the reason in the plan.',
    group: 'plan',
    modes: ['repair'],
    defaultOn: { repair: true, protect: false },
    needs: [],
    needsSites: true,
    scenarioOnly: true,
    selects: 'site',
    legend: [{ label: 'Rejected: would block the breeze', color: 'status-rejected', shape: 'line' }],
    render: renderRejected,
  },
  {
    id: 'parcels',
    label: 'Vacant parcels',
    description: 'Plots where a proposed building can be tested.',
    group: 'context',
    modes: ['protect'],
    defaultOn: { repair: false, protect: true },
    needs: ['parcels'],
    selects: 'parcel',
    legend: [{ label: 'Vacant parcel', color: 'map-parcel', shape: 'fill' }],
    render: renderParcels,
  },
  {
    id: 'buildings',
    label: 'Buildings (3D)',
    description: 'Building heights. Most use a default height until Open Buildings data is added.',
    group: 'context',
    defaultOn: { repair: false, protect: true },
    needs: ['buildings'],
    legend: [{ label: 'Building', color: 'map-building', shape: 'fill' }],
    render: renderBuildings,
  },
  {
    id: 'waitPoints',
    label: 'Waiting points',
    description: 'Schools, hospitals, clinics and other places people wait outdoors.',
    group: 'context',
    defaultOn: { repair: true, protect: false },
    needs: ['waitPoints'],
    selects: 'waitPoint',
    legend: [{ label: 'Waiting point', color: 'map-wait-point', shape: 'dot' }],
    render: renderWaitPoints,
  },
] as const satisfies readonly LayerDef[]

export type LayerId = (typeof LAYERS)[number]['id']

const DEFS = LAYERS as readonly LayerDef[]

/** Layers that exist in a mode, in registry order. */
export function layersFor(mode: Mode): LayerDef[] {
  return DEFS.filter((l) => !l.modes || l.modes.includes(mode))
}

/** Legend entries for a mode, keeping change-kind entries only when the scenario has that kind. */
export function legendOf(layer: LayerDef, mode: Mode, changes: Change[] = []): LegendEntry[] {
  const entries = Array.isArray(layer.legend) ? layer.legend : layer.legend[mode]
  return entries.filter((e) => !e.changeKind || changes.some((c) => c.kind === e.changeKind))
}

export function defaultVisibility(mode: Mode): Record<LayerId, boolean> {
  return Object.fromEntries(DEFS.map((l) => [l.id, l.defaultOn[mode]])) as Record<LayerId, boolean>
}

/** Each deck.gl layer id starts with its registry id (sub-layers append a suffix). */
export function layerDefById(deckLayerId: string): LayerDef | undefined {
  return DEFS.find((l) => deckLayerId === l.id || deckLayerId.startsWith(`${l.id}-`))
}
