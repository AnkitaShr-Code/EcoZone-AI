// The one interface every data adapter implements. Components never import an
// adapter directly; they use the hooks in ./hooks.ts, which call `api`.

import type { AreaResult, AreaSummary, Change, Explanation, Hotspot, LayerData, LayerName, SearchEvent, SearchRequest, Site, UnitCosts } from './types'
import { httpApi } from './http/httpApi'
import { mockApi } from './mock/mockApi'

export interface EcoZoneApi {
  getArea(areaId: string): Promise<AreaSummary>
  getLayer<K extends LayerName>(areaId: string, name: K): Promise<LayerData[K]>
  getHotspots(areaId: string): Promise<Hotspot[]>
  getSites(areaId: string): Promise<Site[]>
  /** Instant, engine only (ARCHITECTURE.md rule 1). */
  rescore(areaId: string, changes: Change[], unitCosts: UnitCosts): Promise<AreaResult>
  /** Agent run: the shared propose → score → judge loop, streamed. */
  runSearch(areaId: string, request: SearchRequest, signal: AbortSignal): AsyncIterable<SearchEvent>
  /** Agent run: plain-language drivers for a scored change set. */
  explain(areaId: string, changes: Change[], unitCosts: UnitCosts): Promise<Explanation>
}

const mode = import.meta.env.VITE_API_MODE ?? 'mock'

function select(): EcoZoneApi {
  if (mode === 'mock') return mockApi
  if (mode === 'http') return httpApi
  throw new Error(`VITE_API_MODE=${mode} is not a mode. Use "mock" or "http".`)
}

export const api = select()
export const isMockData = mode === 'mock'
