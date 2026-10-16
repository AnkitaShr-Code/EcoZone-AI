import { Check, CircleAlert, Loader2, Square } from 'lucide-react'
import type { SearchState } from '@/api/hooks'
import type { Candidate } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface SearchProgressProps {
  state: SearchState | undefined
  running: boolean
  failed?: boolean
  /** Short label of what the score means, for example "Area cooling score". */
  scoreLabel: string
  formatScore: (c: Candidate) => string
  /** Which candidate counts as best so far. */
  isBetter: (a: Candidate, b: Candidate) => boolean
  baselineLabel: string
  onStop?: () => void
}

/** Live progress of a propose → score → refine search, shared by Repair and Protect. */
export function SearchProgress({ state, running, failed, scoreLabel, formatScore, isBetter, baselineLabel, onStop }: SearchProgressProps) {
  const candidates = state?.rounds.flatMap((r) => r.candidates) ?? []
  const best = candidates.filter((c) => c.valid).reduce<Candidate | null>((a, c) => (!a || isBetter(c, a) ? c : a), null)
  const roundNow = state?.rounds.length ?? 0

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-center gap-2 text-sm">
        {failed
          ? <CircleAlert className="size-4 text-delta-worse" aria-hidden />
          : running ? <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden /> : <Check className="size-4 text-delta-better" aria-hidden />}
        <p className="flex-1" aria-live="polite">
          {failed ? "The search stopped with an error. Try drafting again." : running
            ? roundNow ? `Round ${roundNow} of up to 3 · ${candidates.length} options scored` : 'Preparing the search…'
            : `Search finished · ${candidates.length} options scored in ${roundNow} rounds`}
        </p>
        {running && onStop && (
          <Button variant="outline" size="sm" onClick={onStop}>
            <Square className="size-3" aria-hidden /> Stop
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground">Gemini proposes options; the engine scores every one. {scoreLabel} shown.</p>
      {state?.error && <p className="text-xs text-delta-worse">{state.error.message} The best option scored so far is kept.</p>}
      {state?.usedTemplate && <p className="text-xs text-muted-foreground">The explanation failed the number check, so it was written from engine values instead.</p>}

      <ol className="space-y-2 text-xs">
        {state?.baseline && (
          <li className="flex items-center justify-between rounded-md bg-muted/60 px-2 py-1.5">
            <span>{baselineLabel}</span>
            <span className="font-semibold tabular-nums">{formatScore(state.baseline)}</span>
          </li>
        )}
        {state?.rounds.map((r) => (
          <li key={r.round}>
            <p className="mb-1 font-semibold text-muted-foreground">Round {r.round}</p>
            <ul className="space-y-1">
              {r.candidates.map((c) => (
                <li key={c.id} className={cn('flex items-center justify-between gap-2 rounded-md px-2 py-1', c.id === best?.id ? 'bg-delta-better/10' : 'bg-muted/40', !c.valid && 'opacity-60')}>
                  <span className="truncate">
                    {c.id === best?.id && <Check className="mr-1 inline size-3 text-delta-better" aria-label="Best so far" />}
                    {c.label}
                    {!c.valid && c.invalidReason && <span className="text-muted-foreground"> · {c.invalidReason}</span>}
                  </span>
                  <span className="shrink-0 font-semibold tabular-nums">{formatScore(c)}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
