// TanStack Query hooks: the only way components read server data (UI_RULES.md §8).

import { experimental_streamedQuery as streamedQuery, keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { api } from './client'
import { changesKey } from './keys'
import type { Candidate, Change, LayerName, SearchEvent, SearchRequest, SearchResult, UnitCosts } from './types'

const STATIC = { staleTime: Infinity, gcTime: Infinity } as const

export function useArea(areaId: string) {
  return useQuery({ queryKey: ['area', areaId], queryFn: () => api.getArea(areaId), ...STATIC })
}

export function useLayer<K extends LayerName>(areaId: string, name: K, enabled = true) {
  return useQuery({ queryKey: ['layer', areaId, name], queryFn: () => api.getLayer(areaId, name), enabled, ...STATIC })
}

export function useHotspots(areaId: string) {
  return useQuery({ queryKey: ['hotspots', areaId], queryFn: () => api.getHotspots(areaId), ...STATIC })
}

export function useSites(areaId: string, enabled = true) {
  return useQuery({ queryKey: ['sites', areaId], queryFn: () => api.getSites(areaId), enabled, ...STATIC })
}

/** Instant engine rescore of a change set. Keeps the previous result while a new one loads. */
export function useRescore(areaId: string, changes: Change[], unitCosts: UnitCosts | null | undefined, enabled = true) {
  return useQuery({
    queryKey: ['rescore', areaId, changesKey(changes), unitCosts],
    queryFn: () => api.rescore(areaId, changes, unitCosts as UnitCosts),
    enabled: enabled && !!unitCosts && changes.length > 0,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}

/** Accumulated state of one streamed search run. */
export interface SearchState {
  baseline: Candidate | null
  rounds: { round: number; candidates: Candidate[] }[]
  result: SearchResult | null
}

const EMPTY_SEARCH: SearchState = { baseline: null, rounds: [], result: null }

function reduceSearch(state: SearchState, event: SearchEvent): SearchState {
  switch (event.type) {
    case 'baseline':
      return { ...state, baseline: event.candidate }
    case 'round':
      return { ...state, rounds: [...state.rounds, { round: event.round, candidates: [] }] }
    case 'candidate':
      return {
        ...state,
        rounds: state.rounds.map((r) => (r.round === event.candidate.round ? { ...r, candidates: [...r.candidates, event.candidate] } : r)),
      }
    case 'done':
      return { ...state, result: event.result }
  }
}

/**
 * One agent search run, streamed. `runId` distinguishes repeated runs with the same
 * request; pass null to stay idle. Cancelled when the component unmounts or the key changes.
 */
export function useSearchRun(areaId: string, request: SearchRequest | null, runId: number | null) {
  return useQuery({
    queryKey: ['search', areaId, runId, request],
    queryFn: streamedQuery<SearchEvent, SearchState>({
      streamFn: ({ signal }) => api.runSearch(areaId, request as SearchRequest, signal),
      reducer: reduceSearch,
      initialValue: EMPTY_SEARCH,
    }),
    enabled: !!request && runId !== null,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  })
}

export function useExplain(areaId: string) {
  return useMutation({
    mutationFn: ({ changes, unitCosts }: { changes: Change[]; unitCosts: UnitCosts }) => api.explain(areaId, changes, unitCosts),
  })
}
