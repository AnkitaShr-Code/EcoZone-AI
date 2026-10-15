import { Check, Loader2, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type StepState = 'done' | 'open' | 'locked'

export interface PrimaryAction {
  label: string
  onClick: () => void
  disabled?: boolean
  /** Shown under the button when it is disabled, so the user knows why. */
  disabledReason?: string
  loading?: boolean
}

interface StepCardProps {
  number: number
  title: string
  state: StepState
  /** Done: one-line summary of the choice. */
  summary?: string
  /** Open: one sentence telling the user what to do. */
  instruction?: string
  /** Locked: why the step can't be opened yet. */
  lockedReason?: string
  /** Done: a later change made this step's result out of date. */
  staleNote?: string
  primary?: PrimaryAction
  onEdit?: () => void
  children?: React.ReactNode
}

/** The one step pattern for every workflow (UI_RULES.md §3). */
export function StepCard({ number, title, state, summary, instruction, lockedReason, staleNote, primary, onEdit, children }: StepCardProps) {
  const open = state === 'open'
  return (
    <section
      aria-current={open ? 'step' : undefined}
      className={cn('rounded-xl border bg-card', open ? 'border-foreground/15 shadow-sm' : 'border-border', state === 'locked' && 'bg-muted/30')}
    >
      <header className="flex items-center gap-3 px-4 py-3">
        <span
          className={cn(
            'flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
            state === 'done' && 'bg-foreground text-background',
            open && 'border-2 border-foreground',
            state === 'locked' && 'border text-muted-foreground',
          )}
          aria-hidden
        >
          {state === 'done' ? <Check className="size-3.5" /> : number}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className={cn('text-base font-semibold leading-tight', state === 'locked' && 'text-muted-foreground')}>
            <span className="sr-only">Step {number}: </span>
            {title}
          </h2>
          {state === 'done' && summary && <p className="truncate text-xs text-muted-foreground">{summary}</p>}
          {state === 'locked' && lockedReason && (
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <Lock className="size-3" aria-hidden /> {lockedReason}
            </p>
          )}
        </div>
        {state === 'done' && onEdit && (
          <Button variant="ghost" size="sm" onClick={onEdit}>
            Edit
          </Button>
        )}
      </header>
      {state === 'done' && staleNote && <p className="px-4 pb-3 text-xs text-delta-worse">{staleNote}</p>}
      {open && (
        <div className="space-y-4 px-4 pb-4">
          {instruction && <p className="text-sm text-muted-foreground">{instruction}</p>}
          {children}
          {primary && (
            <div className="space-y-1.5">
              <Button className="w-full" size="lg" onClick={primary.onClick} disabled={primary.disabled || primary.loading}>
                {primary.loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
                {primary.label}
              </Button>
              {primary.disabled && primary.disabledReason && (
                <p className="text-center text-xs text-muted-foreground">{primary.disabledReason}</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
