// Protect planner inputs and the active design search (UI state).

import { create } from 'zustand'
import type { BuildingDesign, DesignOption, SearchRequest } from '@/api/types'

/** Option C must keep at least this share of A's floor area (prototype setting, docs/PLANNING.md). */
export const MIN_FLOOR_AREA_PCT = 40
export const BUILDOUT_RADII_M = [200, 400, 600] as const

interface ProtectState {
  parcelId: string | null
  design: BuildingDesign | null
  /** Option B must keep at least this share of A's floor area (planner input). */
  keepFloorAreaPct: number
  run: { id: number; request: Extract<SearchRequest, { mode: 'protect' }> } | null
  chosen: DesignOption['key'] | null
  buildout: { radiusM: number; ran: boolean }
  setParcel: (parcelId: string, design: BuildingDesign) => void
  setDesign: (patch: Partial<BuildingDesign>) => void
  setKeepFloorAreaPct: (value: number) => void
  startSearch: () => void
  choose: (option: DesignOption) => void
  setBuildout: (patch: Partial<ProtectState['buildout']>) => void
}

export const useProtectStore = create<ProtectState>((set) => ({
  parcelId: null,
  design: null,
  keepFloorAreaPct: 80,
  run: null,
  chosen: null,
  buildout: { radiusM: 400, ran: false },
  setParcel: (parcelId, design) => set({ parcelId, design, run: null, chosen: null, buildout: { radiusM: 400, ran: false } }),
  setDesign: (patch) => set((s) => (s.design ? { design: { ...s.design, ...patch } } : s)),
  setKeepFloorAreaPct: (keepFloorAreaPct) => set({ keepFloorAreaPct }),
  startSearch: () => set((s) => (s.parcelId && s.design
    ? {
      run: { id: Date.now(), request: { mode: 'protect', parcelId: s.parcelId, proposal: s.design, keepFloorAreaPct: s.keepFloorAreaPct, minFloorAreaPct: MIN_FLOOR_AREA_PCT } },
      chosen: null,
    }
    : s)),
  choose: (option) => set({ chosen: option.key, design: option.design }),
  setBuildout: (patch) => set((s) => ({ buildout: { ...s.buildout, ...patch } })),
}))
