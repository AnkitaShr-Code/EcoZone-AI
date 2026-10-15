// Shared deck.gl settings for layer render functions.

import type { SelectionKind } from '@/state/uiStore'

/** Ground layers draw without depth testing so they don't z-fight; 3D layers still occlude them. */
export const GROUND_PARAMETERS = { depthCompare: 'always', depthWriteEnabled: false } as const

export const isSelected = (selection: { kind: string; id: string } | null, kind: string, id: string) =>
  selection?.kind === kind && selection.id === id

/**
 * What a pickable datum carries so clicks and tooltips work: an id, a display name, and
 * optionally a selection kind that overrides the layer's default (UI_RULES.md §4).
 */
export interface Pickable {
  id: string
  name?: string | null
  selectKind?: SelectionKind
}

/** Reads the pickable fields from a plain datum or a GeoJSON feature. */
export function pickableOf(object: unknown): Pickable | null {
  if (!object || typeof object !== 'object') return null
  const o = object as { properties?: Partial<Pickable> } & Partial<Pickable>
  const p = o.properties ?? o
  return typeof p.id === 'string' ? { id: p.id, name: p.name, selectKind: p.selectKind } : null
}
