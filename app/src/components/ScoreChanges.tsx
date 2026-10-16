import type { IndexKey } from '@/api/types'
import { Stat } from './Stat'

type Key = IndexKey | 'acs'

/** Before and after for a set of indices, in a two-column grid. */
export function ScoreChanges({ before, after, indices }: { before: Partial<Record<Key, number>>; after: Partial<Record<Key, number>>; indices: Key[] }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {indices.map((k) => (after[k] === undefined ? null : <Stat key={k} index={k} value={after[k] as number} before={before[k]} />))}
    </div>
  )
}
