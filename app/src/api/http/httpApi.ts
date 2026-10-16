// HTTP adapter: the FastAPI service (api/RULES.md, routes). Same interface as the mock adapter;
// no values are computed here. Errors arrive as the contract's ErrorBody and surface as ApiError.

import type { EcoZoneApi } from '../client'
import type { ErrorBody, LayerData, LayerName, SearchEvent, ShadeTime } from '../types'
import { readEvents } from './sse'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'
const SHADE_TIMES: ShadeTime[] = ['13:00', '15:00', '16:00']
/** Reconnect attempts for a dropped event stream; the server replays from Last-Event-ID. */
const STREAM_RETRIES = 3

export class ApiError extends Error {
  readonly code: ErrorBody['error']['code']
  readonly status: number

  constructor(code: ErrorBody['error']['code'], message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {}
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: { Accept: 'application/json', ...(json === undefined ? {} : { 'Content-Type': 'application/json' }), ...rest.headers },
    body: json === undefined ? rest.body : JSON.stringify(json),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ErrorBody | null
    throw new ApiError(body?.error.code ?? 'INTERNAL', body?.error.message ?? `The server returned ${res.status}.`, res.status)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const area = (areaId: string) => `/areas/${encodeURIComponent(areaId)}`

async function shadows(areaId: string): Promise<LayerData['shadows']> {
  const layers = await Promise.all(
    SHADE_TIMES.map((t) => request<LayerData['shadows'][ShadeTime]>(`${area(areaId)}/shadows?t=${encodeURIComponent(t)}`)),
  )
  return Object.fromEntries(SHADE_TIMES.map((t, i) => [t, layers[i]])) as LayerData['shadows']
}

async function* streamRun(runId: string, signal: AbortSignal): AsyncGenerator<SearchEvent> {
  let lastSeq = 0
  let finished = false
  for (let attempt = 0; attempt <= STREAM_RETRIES && !finished; attempt++) {
    try {
      const res = await fetch(`${BASE}/runs/${runId}/events`, {
        headers: { Accept: 'text/event-stream', ...(lastSeq ? { 'Last-Event-ID': String(lastSeq) } : {}) },
        signal,
      })
      if (!res.ok || !res.body) throw new ApiError('INTERNAL', `The search stream returned ${res.status}.`, res.status)
      for await (const data of readEvents(res.body)) {
        const event = JSON.parse(data) as SearchEvent
        lastSeq = event.seq
        attempt = 0
        yield event
        if (event.type === 'done') finished = true
      }
      // A stream that ends cleanly means the run is over, with or without a done event.
      finished = true
    } catch (error) {
      if (signal.aborted || attempt === STREAM_RETRIES) throw error
    }
  }
}

export const httpApi: EcoZoneApi = {
  getArea: (areaId) => request(area(areaId)),
  getLayer: async <K extends LayerName>(areaId: string, name: K) => {
    if (name === 'shadows') return (await shadows(areaId)) as LayerData[K]
    return request<LayerData[K]>(`${area(areaId)}/layers/${name}`)
  },
  getHotspots: (areaId) => request(`${area(areaId)}/hotspots`),
  getSites: (areaId) => request(`${area(areaId)}/sites`),
  rescore: (areaId, changes, unitCosts) => request(`${area(areaId)}/rescore`, { method: 'POST', json: { changes, unitCosts } }),
  runSearch: async function* (areaId, searchRequest, signal) {
    const { runId } = await request<{ runId: string }>(`${area(areaId)}/runs`, { method: 'POST', json: searchRequest, signal })
    // Stopping keeps the best result so far on the server; the client stops listening.
    const stop = () => void fetch(`${BASE}/runs/${runId}`, { method: 'DELETE', keepalive: true }).catch(() => undefined)
    signal.addEventListener('abort', stop, { once: true })
    try {
      yield* streamRun(runId, signal)
    } finally {
      signal.removeEventListener('abort', stop)
    }
  },
  explain: (areaId, changes, unitCosts) => request(`${area(areaId)}/explain`, { method: 'POST', json: { changes, unitCosts } }),
}
