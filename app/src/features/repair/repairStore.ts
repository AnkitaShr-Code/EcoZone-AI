// Repair planner inputs (UI state, labelled planner input in the UI).

import { create } from 'zustand'
import type { InterventionType, UnitCosts } from '@/api/types'

interface RepairState {
  budgetLakh: number
  /** Null until the area's defaults load; then the planner can edit them. */
  unitCosts: UnitCosts | null
  edited: Partial<Record<InterventionType, boolean>>
  setBudgetLakh: (value: number) => void
  initUnitCosts: (defaults: UnitCosts) => void
  setUnitCost: (type: InterventionType, inr: number) => void
}

export const useRepairStore = create<RepairState>((set) => ({
  budgetLakh: 25,
  unitCosts: null,
  edited: {},
  setBudgetLakh: (budgetLakh) => set({ budgetLakh }),
  initUnitCosts: (defaults) => set((s) => (s.unitCosts ? s : { unitCosts: defaults })),
  setUnitCost: (type, inr) => set((s) => (s.unitCosts
    ? { unitCosts: { ...s.unitCosts, [type]: { ...s.unitCosts[type], inr } }, edited: { ...s.edited, [type]: true } }
    : s)),
}))
