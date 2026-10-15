import type { BlockProps, SegmentProps, WaitPointProps } from '@/api/types'
import { formatShadeTime } from '@/lib/format'
import { PRIORITY_META, WAIT_POINT_LABEL } from '@/lib/meta'
import type { SelectionKind } from '@/state/uiStore'

/** One line of name plus one value (UI_RULES.md §4). */
export function tooltipText(kind: SelectionKind, props: unknown, shadeIndex: number, shadeTime: string): string {
  if (kind === 'block') {
    const p = props as BlockProps
    return `Block ${p.id.slice(2)}\n${PRIORITY_META[p.priorityClass].label}`
  }
  if (kind === 'segment') {
    const p = props as SegmentProps
    return `${p.road ?? `Unnamed ${p.roadClass} road`}\nFootpath ${p.shaded[shadeIndex] ? 'in shade' : 'in sun'} at ${formatShadeTime(shadeTime)}`
  }
  const p = props as WaitPointProps
  return `${p.name ?? WAIT_POINT_LABEL[p.type] ?? p.type}\n${WAIT_POINT_LABEL[p.type] ?? p.type}`
}
