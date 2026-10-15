import type { BuildingDesign, Change } from './types'

/** A proposed building on a parcel, as an engine change (docs/DESIGN.md, Change). */
export function buildingChange(parcelId: string, design: BuildingDesign): Change {
  return {
    kind: 'building',
    siteId: parcelId,
    quantity: design.floors,
    params: { footprintPct: design.footprintPct, greenPct: design.greenPct, orientationDeg: design.orientationDeg },
  }
}
