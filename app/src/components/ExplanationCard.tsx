import { Sparkles } from 'lucide-react'
import type { Explanation } from '@/api/types'

/** Text written by the agent from engine scores; the output guard checks every number. */
export function ExplanationCard({ explanation, staleNote }: { explanation: Explanation; staleNote?: string }) {
  return (
    <section className="space-y-2 rounded-lg border bg-prov-ai/5 p-3 text-sm" aria-label="Explanation">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-prov-ai">
        <Sparkles className="size-3.5" aria-hidden />
        {explanation.source === 'template' ? 'Explanation from engine values' : 'Explanation written by Gemini. Every number comes from the engine.'}
      </p>
      {explanation.paragraphs.map((p) => <p key={p}>{p}</p>)}
      {staleNote && <p className="text-xs text-delta-worse">{staleNote}</p>}
    </section>
  )
}
