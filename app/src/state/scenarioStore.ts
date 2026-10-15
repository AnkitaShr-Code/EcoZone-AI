// The working scenario per mode: the change set the planner is looking at (a
// Repair plan or a Protect proposal / build-out). It is planner-owned state,
// initialised from a search result and then edited; its scores always come
// from the rescore query, never from here (UI_RULES.md §8).

import { create } from 'zustand'
import type { Change, Mode, RejectedOption } from '@/api/types'

export type MapView = 'today' | 'scenario'

interface Scenario {
  changes: Change[]
  /** Options the engine rejected, shown on the map and in the plan for transparency. */
  rejected: RejectedOption[]
}

interface ScenarioState {
  scenario: Record<Mode, Scenario>
  view: MapView
  setChanges: (mode: Mode, changes: Change[], rejected?: RejectedOption[]) => void
  toggleChange: (mode: Mode, change: Change) => void
  clear: (mode: Mode) => void
  setView: (view: MapView) => void
}

const EMPTY: Scenario = { changes: [], rejected: [] }

export const useScenarioStore = create<ScenarioState>((set) => ({
  scenario: { repair: EMPTY, protect: EMPTY },
  view: 'today',
  setChanges: (mode, changes, rejected) => set((s) => ({
    scenario: { ...s.scenario, [mode]: { changes, rejected: rejected ?? s.scenario[mode].rejected } },
    view: changes.length ? 'scenario' : 'today',
  })),
  toggleChange: (mode, change) => set((s) => {
    const current = s.scenario[mode].changes
    const exists = current.some((c) => c.siteId === change.siteId)
    const changes = exists ? current.filter((c) => c.siteId !== change.siteId) : [...current, change]
    return { scenario: { ...s.scenario, [mode]: { ...s.scenario[mode], changes } } }
  }),
  clear: (mode) => set((s) => ({ scenario: { ...s.scenario, [mode]: EMPTY }, view: 'today' })),
  setView: (view) => set({ view }),
}))
