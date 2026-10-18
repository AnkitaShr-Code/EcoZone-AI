import { CircleHelp, Leaf, ShieldCheck, Wrench } from 'lucide-react'
import { isMockData } from '@/api/client'
import { useArea } from '@/api/hooks'
import type { Mode } from '@/api/types'
import { Provenance } from '@/components/Provenance'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useUiStore } from '@/state/uiStore'

const MODES: { value: Mode; label: string; icon: typeof Wrench; hint: string }[] = [
  { value: 'repair', label: 'Repair', icon: Wrench, hint: 'Cool the streets people already use' },
  { value: 'protect', label: 'Protect', icon: ShieldCheck, hint: 'Check a proposed building before approval' },
]

export function TopBar() {
  const areaId = useUiStore((s) => s.areaId)
  const mode = useUiStore((s) => s.mode)
  const setMode = useUiStore((s) => s.setMode)
  const { data: area } = useArea(areaId)

  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b bg-background px-4">
      <span className="flex items-center gap-2">
        <Leaf className="size-4 text-data-shade" aria-hidden />
        <span className="font-semibold">EcoZone AI</span>
        <span className="hidden text-xs text-muted-foreground xl:inline">Cooling analytics for urban heat</span>
      </span>

      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={mode}
        onValueChange={(v) => v && setMode(v as Mode)}
        aria-label="Mode"
      >
        {MODES.map(({ value, label, icon: Icon, hint }) => (
          <ToggleGroupItem key={value} value={value} title={hint} className="px-3">
            <Icon className="size-4" aria-hidden />
            {label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <Select value={areaId} disabled={!area}>
        <SelectTrigger size="sm" className="min-w-0 w-64 sm:w-80 lg:w-96" aria-label="Area">
          <SelectValue placeholder="Loading area…" />
        </SelectTrigger>
        <SelectContent>
          {area && <SelectItem value={area.id}>{area.name}, {area.city}</SelectItem>}
        </SelectContent>
      </Select>

      <div className="ml-auto flex items-center gap-2">
        {isMockData && <Provenance kind="mock" detail="scores and costs are not real" />}
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="How to use EcoZone AI">
              <CircleHelp className="size-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 text-sm">
            <ol className="list-decimal space-y-1.5 pl-4">
              <li>Pick a mode: Repair cools existing streets; Protect checks a proposed building.</li>
              <li>Work through the steps on the left. The open step's button always says what happens next.</li>
              <li>Click the map to inspect a block, footpath or waiting point. Press Esc to clear.</li>
              <li>Use Layers (top right of the map) to show or hide what you need.</li>
            </ol>
          </PopoverContent>
        </Popover>
      </div>
    </header>
  )
}
