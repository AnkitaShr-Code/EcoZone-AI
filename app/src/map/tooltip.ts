import type { BlockProps, ParcelProps, SegmentProps, WaitPointProps } from '@/api/types'
import { formatShadeTime } from '@/lib/format'
import { PRIORITY_META, WAIT_POINT_LABEL } from '@/lib/meta'
import type { SelectionKind } from '@/state/uiStore'

/** Name plus one value (UI_RULES.md §4). `props` is the feature's properties or the datum. */
export function tooltipText(kind: SelectionKind, props: unknown, shadeIndex: number, shadeTime: string): string {
  switch (kind) {
    case 'block': {
      const p = props as BlockProps
      return `Block ${p.id.slice(2)}\n${PRIORITY_META[p.priorityClass].label}`
    }
    case 'segment': {
      const p = props as SegmentProps
      return `${p.road ?? `Unnamed ${p.roadClass} road`}\nFootpath ${p.shaded[shadeIndex] ? 'in shade' : 'in sun'} at ${formatShadeTime(shadeTime)}`
    }
    case 'waitPoint': {
      const p = props as WaitPointProps
      const type = WAIT_POINT_LABEL[p.type] ?? p.type
      return `${p.name ?? type}\n${type}`
    }
    case 'parcel': {
      const p = props as ParcelProps
      return `${p.name}\nClick to select`
    }
    case 'site': {
      const p = props as { name?: string }
      return `${p.name ?? 'Site'}\nClick for details`
    }
  }
}
