// Unit costs: planner input shared by the Repair budget step, the plan search and
// every rescore of a plan (labelled planner input or default in the UI).

import { create } from 'zustand'
import type { InterventionType, UnitCosts } from '@/api/types'

interface CostsState {
  /** Null until the area's defaults load. */
  unitCosts: UnitCosts | null
  edited: Partial<Record<InterventionType, boolean>>
  initUnitCosts: (defaults: UnitCosts) => void
  setUnitCost: (type: InterventionType, inr: number) => void
}

export const useCostsStore = create<CostsState>((set) => ({
  unitCosts: null,
  edited: {},
  initUnitCosts: (defaults) => set((s) => (s.unitCosts ? s : { unitCosts: defaults })),
  setUnitCost: (type, inr) => set((s) => (s.unitCosts
    ? { unitCosts: { ...s.unitCosts, [type]: { ...s.unitCosts[type], inr } }, edited: { ...s.edited, [type]: true } }
    : s)),
}))
