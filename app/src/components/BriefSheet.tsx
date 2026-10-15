import { createPortal } from 'react-dom'
import { isMockData } from '@/api/client'

/**
 * A printable brief. Rendered into #print-root (outside the app) and shown only when
 * printing; "Download brief" calls window.print(), and the browser saves it as a PDF.
 */
export function BriefSheet({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  const root = document.getElementById('print-root')
  if (!root) return null
  return createPortal(
    <article className="mx-auto max-w-3xl space-y-6 p-8 text-sm text-foreground">
      <header className="border-b pb-4">
        <p className="text-xs text-muted-foreground">EcoZone AI · decision support, the planner decides</p>
        <h1 className="mt-1 text-2xl font-semibold">{title}</h1>
        <p className="text-muted-foreground">{subtitle}</p>
        {isMockData && <p className="mt-2 font-semibold text-prov-mock">Mock data: scores, costs and effects in this brief are not real.</p>}
      </header>
      {children}
      <footer className="border-t pt-4 text-xs text-muted-foreground">
        Scores are 0–100 screening indicators for comparing options in the same area, not measurements of temperature or wind.
        Costs come from planner unit costs, not market prices.
      </footer>
    </article>,
    root,
  )
}

export function BriefSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2 break-inside-avoid">
      <h2 className="text-base font-semibold">{title}</h2>
      {children}
    </section>
  )
}
