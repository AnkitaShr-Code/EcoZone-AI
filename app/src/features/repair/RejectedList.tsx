import { TriangleAlert } from 'lucide-react'
import type { RejectedOption, Site } from '@/api/types'
import { centerOf } from '@/lib/geo'
import { flyTo } from '@/map/mapController'
import { useUiStore } from '@/state/uiStore'

/** Options the engine rejected, with the reason, so the planner sees what was ruled out and why. */
export function RejectedList({ rejected, sites }: { rejected: RejectedOption[]; sites: Map<string, Site> }) {
  const select = useUiStore((s) => s.select)
  if (!rejected.length) return null
  return (
    <section aria-label="Rejected options">
      <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
        <TriangleAlert className="size-4 text-status-rejected" aria-hidden />
        Rejected by the ventilation check
      </h3>
      <ul className="space-y-2">
        {rejected.map((r) => {
          const site = sites.get(r.siteId)
          if (!site) return null
          return (
            <li key={r.siteId} className="rounded-lg border border-status-rejected/30 bg-status-rejected/5 px-3 py-2 text-sm">
              <button
                type="button"
                className="text-left font-semibold hover:underline"
                onClick={() => {
                  select({ kind: 'site', id: site.id })
                  flyTo(centerOf(site.geometry), 17.5)
                }}
              >
                {site.name}
              </button>
              <p className="text-xs text-muted-foreground">{r.reason} A shade structure works better here.</p>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
