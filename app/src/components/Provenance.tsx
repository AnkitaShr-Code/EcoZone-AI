import { cn } from '@/lib/utils'

export type ProvenanceKind = 'planner' | 'ai' | 'default' | 'mock'

const TEXT: Record<ProvenanceKind, string> = {
  planner: 'Planner input',
  ai: 'AI-estimated',
  default: 'Default',
  mock: 'Mock data',
}

const TONE: Record<ProvenanceKind, string> = {
  planner: 'text-prov-planner border-prov-planner/30 bg-prov-planner/5',
  ai: 'text-prov-ai border-prov-ai/30 bg-prov-ai/5',
  default: 'text-prov-default border-prov-default/30 bg-prov-default/5',
  mock: 'text-prov-mock border-prov-mock/30 bg-prov-mock/10',
}

/** The one label for where a value came from (UI_RULES.md §7). */
export function Provenance({ kind, detail, className }: { kind: ProvenanceKind; detail?: string; className?: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs whitespace-nowrap', TONE[kind], className)}>
      {TEXT[kind]}
      {detail && <span className="ml-1 opacity-80">· {detail}</span>}
    </span>
  )
}
