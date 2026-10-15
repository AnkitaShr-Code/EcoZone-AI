import { formatDelta } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * A change with arrow and sign first, colour second (UI_RULES.md §6).
 * `better` says which direction is an improvement for this value.
 */
export function Delta({ value, better, className }: { value: number; better: 'up' | 'down'; className?: string }) {
  const rounded = Math.round(value)
  const improved = rounded !== 0 && (better === 'up' ? rounded > 0 : rounded < 0)
  const tone = rounded === 0 ? 'text-muted-foreground' : improved ? 'text-delta-better' : 'text-delta-worse'
  return (
    <span className={cn('text-sm font-semibold tabular-nums', tone, className)}>
      {formatDelta(value)}
      <span className="sr-only">{rounded === 0 ? '' : improved ? ', better' : ', worse'}</span>
    </span>
  )
}
