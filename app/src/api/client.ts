// The one interface every data adapter implements. Components never import an
// adapter directly; they use the hooks in ./hooks.ts, which call `api`.

import type { AreaResult, AreaSummary, Change, Hotspot, LayerData, LayerName, Site, UnitCosts } from './types'
import { mockApi } from './mock/mockApi'

export interface EcoZoneApi {
  getArea(areaId: string): Promise<AreaSummary>
  getLayer<K extends LayerName>(areaId: string, name: K): Promise<LayerData[K]>
  getHotspots(areaId: string): Promise<Hotspot[]>
  getSites(areaId: string): Promise<Site[]>
  rescore(areaId: string, changes: Change[], unitCosts: UnitCosts): Promise<AreaResult>
}

const mode = import.meta.env.VITE_API_MODE ?? 'mock'

function select(): EcoZoneApi {
  if (mode === 'mock') return mockApi
  throw new Error(`VITE_API_MODE=${mode} is not available yet. Use "mock" until api/http lands.`)
}

export const api = select()
export const isMockData = mode === 'mock'
