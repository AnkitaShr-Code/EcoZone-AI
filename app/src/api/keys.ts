import type { Change } from './types'

/** Stable key for a change set, for query keys and comparisons. */
export function changesKey(changes: Change[]): string {
  return changes.map((c) => `${c.kind}:${c.siteId}:${c.quantity}:${JSON.stringify(c.params ?? {})}`).sort().join('|')
}
