// TanStack Query hooks: the only way components read server data (UI_RULES.md §8).

import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { Change, LayerName, UnitCosts } from './types'

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

export function useSites(areaId: string) {
  return useQuery({ queryKey: ['sites', areaId], queryFn: () => api.getSites(areaId), ...STATIC })
}

export function useRescore(areaId: string) {
  return useMutation({
    mutationFn: ({ changes, unitCosts }: { changes: Change[]; unitCosts: UnitCosts }) => api.rescore(areaId, changes, unitCosts),
  })
}
