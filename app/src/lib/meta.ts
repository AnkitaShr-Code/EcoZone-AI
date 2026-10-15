// Display metadata, defined once: index names, intervention types, driver tags,
// priority classes. Components read labels from here, never hard-code them.

import { Building2, Shovel, Sprout, Trees, Umbrella, type LucideIcon } from 'lucide-react'
import type { IndexKey, InterventionType, PriorityClass, TimeToBenefit } from '@/api/types'
import type { ColorToken } from './colors'

export interface IndexMeta {
  label: string
  description: string
  /** Which direction is an improvement. */
  better: 'up' | 'down'
}

export const INDEX_META: Record<IndexKey | 'acs', IndexMeta> = {
  acs: { label: 'Area cooling score', description: 'Combines heat, footpath shade and green, weighted by where people wait. Higher is better.', better: 'up' },
  pss: { label: 'Footpath shade', description: 'Share of footpath in shadow at 1, 3 and 4 pm on a reference April day. Higher is better.', better: 'up' },
  hei: { label: 'Heat exposure', description: 'How much the area stores heat: paving, missing greenery, building mass and dark roofs. Lower is better.', better: 'down' },
  gcs: { label: 'Green connectivity', description: 'Green cover nearby and how well it links to other green. Higher is better.', better: 'up' },
  vci: { label: 'Ventilation', description: 'How freely air can move along the street corridor. Higher is better.', better: 'up' },
}

/** Display order for score lists. */
export const INDEX_ORDER: (IndexKey | 'acs')[] = ['acs', 'pss', 'hei', 'gcs', 'vci']

export interface InterventionMeta {
  label: string
  icon: LucideIcon
  color: ColorToken
}

export const INTERVENTION_META: Record<InterventionType, InterventionMeta> = {
  tree_row: { label: 'Street tree row', icon: Trees, color: 'iv-tree' },
  shade: { label: 'Shade structure', icon: Umbrella, color: 'iv-shade' },
  depave: { label: 'Depave and plant', icon: Shovel, color: 'iv-depave' },
  pocket_green: { label: 'Pocket green', icon: Sprout, color: 'iv-green' },
  cool_roof: { label: 'Cool roof', icon: Building2, color: 'iv-roof' },
}

export const TIME_TO_BENEFIT_LABEL: Record<TimeToBenefit, string> = {
  weeks: 'Weeks',
  season: 'One season',
  years: 'Years',
}

export const PRIORITY_META: Record<PriorityClass, { label: string; color: ColorToken }> = {
  high: { label: 'High priority', color: 'priority-high' },
  medium: { label: 'Medium priority', color: 'priority-medium' },
  low: { label: 'Low priority', color: 'priority-low' },
}

/** Engine driver tags in plain words. Unknown tags fall back to the raw tag. */
export const DRIVER_LABEL: Record<string, string> = {
  IMPERVIOUS_HIGH: 'Mostly paved',
  LOW_SHADE: 'Little afternoon shade',
  WAIT_POINTS: 'People wait nearby',
  DENSE_LOW_RISE: 'Dense low-rise housing',
  LOW_GREEN: 'Little greenery',
  SHADE_GAIN: 'Adds footpath shade',
  GREEN_LINK: 'Links green patches',
  IMPERVIOUS_LOSS: 'Removes paving',
  ALBEDO_GAIN: 'Reflects more sunlight',
  WAIT_POINT_COVERED: 'Shades a waiting point',
  CANOPY_OBSTRUCTION: 'Canopy would block the breeze',
}

export const driverLabel = (tag: string) => DRIVER_LABEL[tag] ?? tag

export const WAIT_POINT_LABEL: Record<string, string> = {
  school: 'School',
  college: 'College',
  hospital: 'Hospital',
  clinic: 'Clinic',
  marketplace: 'Market',
  bus_stop: 'Bus stop',
}
