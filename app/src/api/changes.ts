import type { BuildingChange, BuildingDesign, Change, InterventionChange } from './types'

/** A proposed building on a parcel, as an engine change (contract BuildingChange). */
export function buildingChange(parcelId: string, design: BuildingDesign): BuildingChange {
  return { kind: 'building', siteId: parcelId, design }
}

export function isInterventionChange(change: Change): change is InterventionChange {
  return change.kind !== 'building'
}
