// Repair planner inputs and the active search run (UI state).

import { create } from 'zustand'
import type { SearchRequest, UnitCosts } from '@/api/types'

const LAKH = 1e5

interface RepairState {
  budgetLakh: number
  /** Share of the budget that must help this summer (planner input, docs/PLANNING.md). */
  quickWinSharePct: number
  /** The request and id of the current plan search; null before the first draft. */
  run: { id: number; request: Extract<SearchRequest, { mode: 'repair' }> } | null
  /** The run whose result has been loaded into the working plan. */
  appliedRunId: number | null
  setBudgetLakh: (value: number) => void
  setQuickWinSharePct: (value: number) => void
  startSearch: (unitCosts: UnitCosts) => void
  markApplied: (runId: number) => void
}

export const useRepairStore = create<RepairState>((set) => ({
  budgetLakh: 25,
  quickWinSharePct: 20,
  run: null,
  appliedRunId: null,
  setBudgetLakh: (budgetLakh) => set({ budgetLakh }),
  setQuickWinSharePct: (quickWinSharePct) => set({ quickWinSharePct }),
  startSearch: (unitCosts) => set((s) => ({
    run: { id: Date.now(), request: { mode: 'repair', budgetInr: s.budgetLakh * LAKH, unitCosts, quickWinSharePct: s.quickWinSharePct } },
  })),
  markApplied: (appliedRunId) => set({ appliedRunId }),
}))
