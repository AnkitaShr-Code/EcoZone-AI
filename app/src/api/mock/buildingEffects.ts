// Mock effects of a proposed building on its parcel's block and neighbours.
// Follows the shape of the terms in docs/PLANNING.md (impervious, green, mass,
// obstruction, orientation, built run) with mock inputs. Not engine output.

import type { BlockProps, BuildingDesign, IndexDelta, ParcelProps, ShadeByTime } from '../types'
import type { AreaIndex } from './areaIndex'

const BASE_PLOT = { greenPct: 40, imperviousPct: 60 } // mock: a vacant plot is part green, part bare or paved
const NEIGHBOUR_SHARE = { vci: 0.4, hei: 0.2 }

export interface BuildingEffect {
  blocks: Record<string, IndexDelta>
  segments: Record<string, ShadeByTime>
  drivers: string[]
}

export function designOf(params: Record<string, number | string> | undefined, floors: number): BuildingDesign {
  return {
    floors,
    footprintPct: Number(params?.footprintPct ?? 50),
    greenPct: Number(params?.greenPct ?? 10),
    orientationDeg: Number(params?.orientationDeg ?? 0),
  }
}

export function buildingEffects(index: AreaIndex, parcel: ParcelProps, design: BuildingDesign): BuildingEffect {
  const { engine } = index.area
  const block = index.blockById.get(parcel.blockId) as BlockProps
  const plotShare = Math.min(1, parcel.areaM2 / block.areaM2)
  const heightM = design.floors * engine.metresPerFloor

  // Heat: paving and roof replace open ground; mass adds stored heat.
  const dImpervious = plotShare * (100 - design.greenPct - BASE_PLOT.imperviousPct)
  const dGreen = plotShare * (design.greenPct - BASE_PLOT.greenPct)
  const volume = parcel.areaM2 * (design.footprintPct / 100) * heightM
  const dMass = plotShare * 100 * Math.min(1, volume / engine.vRefM3)
  const dHei = 0.35 * dImpervious - 0.3 * dGreen + 0.2 * dMass

  // Ventilation: height against street width, orientation to the wind, longer built run.
  const r0 = parcel.neighbourHeightM / parcel.roadWidthM
  const r1 = Math.max(r0, heightM / parcel.roadWidthM)
  const dObstruction = -100 * (Math.min(1, r1 / 2.5) - Math.min(1, r0 / 2.5))
  const align = (deg: number) => Math.abs(Math.cos(((deg - engine.windFromDeg) * Math.PI) / 180))
  const dWind = 100 * (align(design.orientationDeg) - align(parcel.streetBearingDeg))
  const dBuiltRun = -0.3 * design.footprintPct
  const dVci = 0.25 * dObstruction + 0.15 * dWind + 0.25 * dBuiltRun

  const dGcs = 0.6 * dGreen

  const blocks: Record<string, IndexDelta> = { [block.id]: { hei: dHei, gcs: dGcs, vci: dVci } }
  for (const id of parcel.nearbyBlocks) {
    blocks[id] = { hei: NEIGHBOUR_SHARE.hei * dHei, gcs: 0, vci: NEIGHBOUR_SHARE.vci * Math.min(0, dVci) }
  }

  const drivers: string[] = []
  if (dVci < 0) drivers.push(0.25 * dObstruction <= Math.min(0.15 * dWind, 0.25 * dBuiltRun) ? 'OBSTRUCTION' : 0.15 * dWind < 0.25 * dBuiltRun ? 'ORIENTATION' : 'BUILT_RUN')
  if (dHei > 0) drivers.push(0.2 * dMass > 0.35 * dImpervious ? 'MASS_GAIN' : 'IMPERVIOUS_GAIN')
  if (dGcs < 0) drivers.push('GREEN_LOSS')

  const segments = shadeLookup(parcel, design, heightM, engine.footprintLevels, engine.heightLevelsM)
  if (Object.keys(segments).length) drivers.push('SHADE_GAIN')
  return { blocks, segments, drivers }
}

/** Nearest precomputed footprint and height level (the engine computes shadows directly). */
function shadeLookup(parcel: ParcelProps, design: BuildingDesign, heightM: number, fps: number[], heights: number[]) {
  const nearest = (levels: number[], v: number) => levels.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a))
  return parcel.shade[`${nearest(fps, design.footprintPct)}_${nearest(heights, heightM)}`] ?? {}
}
