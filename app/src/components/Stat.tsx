import { Info } from 'lucide-react'
import type { IndexKey } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatScore } from '@/lib/format'
import { INDEX_META } from '@/lib/meta'
import { Delta } from './Delta'

/** One index score as "64 / 100", with its definition on hover or focus and an optional change. */
export function Stat({ index, value, before }: { index: IndexKey | 'acs'; value: number; before?: number }) {
  const meta = INDEX_META[index]
  return (
    <div className="rounded-lg bg-muted/60 p-2.5">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {meta.label}
        <Tooltip>
          <TooltipTrigger aria-label={`About ${meta.label}`} className="rounded-sm">
            <Info className="size-3" aria-hidden />
          </TooltipTrigger>
          <TooltipContent className="max-w-60">{meta.description}</TooltipContent>
        </Tooltip>
      </div>
      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        <span className="text-lg font-semibold tabular-nums">{formatScore(value)}</span>
        <span className="text-xs text-muted-foreground">/ 100</span>
        {before !== undefined && <Delta value={value - before} better={meta.better} className="ml-auto text-xs whitespace-nowrap" />}
      </div>
    </div>
  )
}
