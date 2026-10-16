// Mock adapter: serves the files built by scripts/build-mock-data.mjs and stands in
// for the engine (rescore) and the agents (search, explain). The only front-end
// code allowed to calculate values (UI_RULES.md §8). Switch VITE_API_MODE to replace it.

import type { EcoZoneApi } from '../client'
import type { AreaSummary, LayerData, LayerName, ShadeTime, Site } from '../types'
import { buildAreaIndex, type AreaIndex, type MockEngine } from './areaIndex'
import { explainChanges } from './explainMock'
import { rescoreMock } from './rescoreMock'
import { searchMock, sleep } from './searchMock'

const BASE = `${import.meta.env.BASE_URL}mock`
const LAYER_FILES: Record<Exclude<LayerName, 'shadows'>, string> = {
  blocks: 'blocks.json',
  segments: 'segments.json',
  buildings: 'buildings.json',
  waitPoints: 'wait-points.json',
  parcels: 'parcels.json',
}

const files = new Map<string, Promise<unknown>>()
const indexes = new Map<string, Promise<AreaIndex>>()

function latency(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 80 + Math.random() * 120))
}

function file<T>(areaId: string, name: string): Promise<T> {
  const key = `${areaId}/${name}`
  if (!files.has(key)) {
    files.set(key, fetch(`${BASE}/${key}`).then((res) => {
      if (!res.ok) throw new Error(`Mock file ${key} returned ${res.status}`)
      return res.json()
    }))
  }
  return files.get(key) as Promise<T>
}

async function load<T>(areaId: string, name: string): Promise<T> {
  await latency()
  return file<T>(areaId, name)
}

function areaIndex(areaId: string): Promise<AreaIndex> {
  if (!indexes.has(areaId)) {
    indexes.set(areaId, Promise.all([
      file<AreaSummary>(areaId, 'area.json'),
      file<LayerData['blocks']>(areaId, LAYER_FILES.blocks),
      file<LayerData['segments']>(areaId, LAYER_FILES.segments),
      file<Site[]>(areaId, 'sites.json'),
      file<LayerData['parcels']>(areaId, LAYER_FILES.parcels),
      file<MockEngine>(areaId, '_mock-engine.json'),
    ]).then((parts) => buildAreaIndex(...parts)))
  }
  return indexes.get(areaId) as Promise<AreaIndex>
}

async function loadShadows(areaId: string): Promise<LayerData['shadows']> {
  const times: ShadeTime[] = ['13:00', '15:00', '16:00']
  const entries = await Promise.all(times.map(async (t) => [t, await load(areaId, `shadows-${t.replace(':', '')}.json`)] as const))
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
    const index = await areaIndex(areaId)
    await latency()
    return rescoreMock(index, changes, unitCosts)
  },
  runSearch: async function* (areaId, request, signal) {
    yield* searchMock(await areaIndex(areaId), request, signal)
  },
  explain: async (areaId, changes, unitCosts) => {
    const index = await areaIndex(areaId)
    await sleep(900, new AbortController().signal)
    return explainChanges(index, changes, unitCosts)
  },
}
