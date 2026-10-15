// Mock adapter: serves the files built by scripts/build-mock-data.mjs and stands in
// for the engine's rescore. The only front-end code allowed to calculate values
// (UI_RULES.md §8). Delete nothing here when the http adapter lands; switch
// VITE_API_MODE instead.

import type { EcoZoneApi } from '../client'
import type { LayerData, LayerName, ShadeTime } from '../types'
import { rescoreMock } from './rescoreMock'

const BASE = `${import.meta.env.BASE_URL}mock`
const LAYER_FILES: Record<Exclude<LayerName, 'shadows'>, string> = {
  blocks: 'blocks.json',
  segments: 'segments.json',
  buildings: 'buildings.json',
  waitPoints: 'wait-points.json',
}

const cache = new Map<string, Promise<unknown>>()

function latency(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 120 + Math.random() * 180))
}

async function load<T>(areaId: string, file: string): Promise<T> {
  const key = `${areaId}/${file}`
  if (!cache.has(key)) {
    cache.set(key, fetch(`${BASE}/${key}`).then((res) => {
      if (!res.ok) throw new Error(`Mock file ${key} returned ${res.status}`)
      return res.json()
    }))
  }
  await latency()
  return cache.get(key) as Promise<T>
}

async function loadShadows(areaId: string): Promise<LayerData['shadows']> {
  const times: ShadeTime[] = ['13:00', '15:00', '16:00']
  const entries = await Promise.all(times.map(async (t) =>
    [t, await load(areaId, `shadows-${t.replace(':', '')}.json`)] as const))
  return Object.fromEntries(entries) as LayerData['shadows']
}

export const mockApi: EcoZoneApi = {
  getArea: (areaId) => load(areaId, 'area.json'),
  getLayer: async <K extends LayerName>(areaId: string, name: K) => {
    if (name === 'shadows') return (await loadShadows(areaId)) as LayerData[K]
    return load<LayerData[K]>(areaId, LAYER_FILES[name as Exclude<LayerName, 'shadows'>])
  },
  getHotspots: (areaId) => load(areaId, 'hotspots.json'),
  getSites: (areaId) => load(areaId, 'sites.json'),
  rescore: async (areaId, changes, unitCosts) => {
    const [area, blocks, segments, sites] = await Promise.all([
      mockApi.getArea(areaId),
      mockApi.getLayer(areaId, 'blocks'),
      mockApi.getLayer(areaId, 'segments'),
      mockApi.getSites(areaId),
    ])
    return rescoreMock({ area, blocks, segments, sites, changes, unitCosts })
  },
}
