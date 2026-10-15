// Every map data layer, defined once (UI_RULES.md §4). The layers control, the
// legend and the deck.gl layer list are all generated from this array.
// Adding a layer = adding one entry here (plus its render function in ./layers).

import type { Layer } from '@deck.gl/core'
import type { LayerData, LayerName, Mode, ShadeTime } from '@/api/types'
import type { ColorToken } from '@/lib/colors'
import type { Selection, SelectionKind } from '@/state/uiStore'
import { renderBuildings } from './layers/buildings'
import { renderFootpathShade } from './layers/footpathShade'
import { renderPriority } from './layers/priority'
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
}

export interface LayerContext {
  data: Partial<LayerData>
  shadeTime: ShadeTime
  /** Position of shadeTime in AreaSummary.shadeTimes; indexes ShadeByTime arrays. */
  shadeIndex: number
  selection: Selection | null
}

export interface LayerDef {
  id: string
  label: string
  description: string
  group: LayerGroup
  defaultOn: Record<Mode, boolean>
  /** Layer data this layer needs; loaded only while the layer is visible. */
  needs: LayerName[]
  /** Shows the shade-time control while visible. */
  usesShadeTime?: boolean
  /** Clicking a feature selects it as this kind. */
  selects?: SelectionKind
  legend: LegendEntry[]
  render: (ctx: LayerContext) => Layer[]
}

export const LAYERS = [
  {
    id: 'priority',
    label: 'Priority',
    description: 'Where heat, missing shade and waiting people overlap.',
    group: 'analysis',
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
    description: 'Footpath in sun or shade at the selected time.',
    group: 'analysis',
    defaultOn: { repair: true, protect: false },
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
    description: 'Building shadows at the selected time.',
    group: 'analysis',
    defaultOn: { repair: false, protect: true },
    needs: ['shadows'],
    usesShadeTime: true,
    legend: [{ label: 'Building shadow', color: 'map-shadow', shape: 'fill' }],
    render: renderShadows,
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

export function defaultVisibility(mode: Mode): Record<LayerId, boolean> {
  return Object.fromEntries(LAYERS.map((l) => [l.id, l.defaultOn[mode]])) as Record<LayerId, boolean>
}

export function layerDef(id: string): LayerDef | undefined {
  return (LAYERS as readonly LayerDef[]).find((l) => l.id === id)
}
