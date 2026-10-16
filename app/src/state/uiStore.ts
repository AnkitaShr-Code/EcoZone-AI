// UI state only (UI_RULES.md §8): mode, open step, visible layers, selection,
// shade time. Server data stays in TanStack Query.

import { create } from 'zustand'
import type { Mode, ShadeTime } from '@/api/types'
import { defaultVisibility, type LayerId } from '@/map/layerRegistry'

export type SelectionKind = 'block' | 'segment' | 'waitPoint' | 'parcel' | 'site'
export interface Selection {
  kind: SelectionKind
  id: string
}

interface UiState {
  areaId: string
  mode: Mode
  /** Index of the open step per mode. */
  openStep: Record<Mode, number>
  /** Highest step reached per mode; steps after it are locked. */
  reachedStep: Record<Mode, number>
  visibleLayers: Record<LayerId, boolean>
  shadeTime: ShadeTime
  selection: Selection | null
  setMode: (mode: Mode) => void
  openStepAt: (index: number) => void
  advance: () => void
  /** Reopens a step and locks every step after it (their results no longer apply). */
  resetSteps: (mode: Mode, index: number) => void
  setLayerVisible: (id: LayerId, visible: boolean) => void
  setShadeTime: (time: ShadeTime) => void
  select: (selection: Selection | null) => void
}

export const useUiStore = create<UiState>((set) => ({
  areaId: 'deccan',
  mode: 'repair',
  openStep: { repair: 0, protect: 0 },
  reachedStep: { repair: 0, protect: 0 },
  visibleLayers: defaultVisibility('repair'),
  shadeTime: '15:00',
  selection: null,
  setMode: (mode) => set({ mode, visibleLayers: defaultVisibility(mode), selection: null }),
  openStepAt: (index) => set((s) => (index <= s.reachedStep[s.mode] ? { openStep: { ...s.openStep, [s.mode]: index } } : s)),
  advance: () => set((s) => {
    const next = s.openStep[s.mode] + 1
    return {
      openStep: { ...s.openStep, [s.mode]: next },
      reachedStep: { ...s.reachedStep, [s.mode]: Math.max(s.reachedStep[s.mode], next) },
    }
  }),
  resetSteps: (mode, index) => set((s) => ({
    openStep: { ...s.openStep, [mode]: index },
    reachedStep: { ...s.reachedStep, [mode]: index },
  })),
  setLayerVisible: (id, visible) => set((s) => ({ visibleLayers: { ...s.visibleLayers, [id]: visible } })),
  setShadeTime: (shadeTime) => set({ shadeTime }),
  select: (selection) => set({ selection }),
}))
