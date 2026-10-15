import type { RiskInfo, RiskLabel } from '@/api/types'
import { formatScore } from '@/lib/format'
import { INDEX_META } from '@/lib/meta'
import { cn } from '@/lib/utils'

const TONE: Record<RiskLabel, string> = {
  LOW: 'text-risk-low border-risk-low/30 bg-risk-low/5',
  MODERATE: 'text-risk-moderate border-risk-moderate/30 bg-risk-moderate/5',
  HIGH: 'text-risk-high border-risk-high/30 bg-risk-high/5',
}
const WORD: Record<RiskLabel, string> = { LOW: 'Low risk', MODERATE: 'Moderate risk', HIGH: 'High risk' }

/** Risk label in words, with the worst change it comes from (docs/PLANNING.md, risk label). */
export function RiskBadge({ risk, className }: { risk: RiskInfo; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold', TONE[risk.label], className)}>
      {WORD[risk.label]}
      <span className="font-normal">· worst change {formatScore(risk.change)} on {INDEX_META[risk.index].label.toLowerCase()}</span>
    </span>
  )
}
