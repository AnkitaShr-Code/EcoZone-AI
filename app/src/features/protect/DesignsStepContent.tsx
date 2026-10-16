import { Check } from 'lucide-react'
import { ExplanationCard } from '@/components/ExplanationCard'
import { RiskBadge } from '@/components/RiskBadge'
import { SearchProgress } from '@/components/SearchProgress'
import { formatDesign, formatScore } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useProtectStore } from './protectStore'
import type { ProtectSearch } from './useProtectSearch'

/** Step 3: live design search, then options A, B and C to choose from. */
export function DesignsStepContent({ search }: { search: ProtectSearch }) {
  const chosen = useProtectStore((s) => s.chosen)
  const choose = useProtectStore((s) => s.choose)

  const progress = (
    <SearchProgress
      state={search.state}
      running={search.running}
      failed={search.failed}
      scoreLabel="Worst change on the parcel's block (lower is better)"
      formatScore={(c) => `${formatScore(c.score)} · ${c.floorAreaPct}%`}
      isBetter={(a, b) => a.score < b.score}
      baselineLabel="Option A: as proposed"
      onStop={search.stop}
    />
  )
  if (!search.result?.options) return progress

  return (
    <div className="space-y-4">
      <details>
        <summary className="cursor-pointer text-xs text-muted-foreground">Show search details</summary>
        <div className="mt-2">{progress}</div>
      </details>

      <div role="radiogroup" aria-label="Design options" className="space-y-2">
        {search.result.options.map((o) => {
          const on = chosen === o.key
          return (
            <button
              key={o.key}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => choose(o)}
              className={cn('w-full space-y-1.5 rounded-lg border p-3 text-left hover:bg-muted/40', on && 'border-foreground/40 bg-muted/40')}
            >
              <span className="flex items-center justify-between text-sm font-semibold">
                Option {o.key} · {o.title}
                {on && <Check className="size-4" aria-hidden />}
              </span>
              <span className="block text-xs text-muted-foreground">{formatDesign(o.design)}</span>
              {o.candidate.risk && <RiskBadge risk={o.candidate.risk} />}
              <span className="block text-xs">{o.tradeOff}</span>
            </button>
          )
        })}
      </div>

      <ExplanationCard explanation={search.result.explanation} />
    </div>
  )
}
