import { Sun } from 'lucide-react'
import { useArea } from '@/api/hooks'
import type { ShadeTime } from '@/api/types'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatReferenceDate, formatShadeTime } from '@/lib/format'
import { useUiStore } from '@/state/uiStore'
import { LAYERS } from './layerRegistry'

/** Only the engine's reference times; shown only while a shade layer is visible (UI_RULES.md §4). */
export function TimeControl() {
  const areaId = useUiStore((s) => s.areaId)
  const visible = useUiStore((s) => s.visibleLayers)
  const shadeTime = useUiStore((s) => s.shadeTime)
  const setShadeTime = useUiStore((s) => s.setShadeTime)
  const { data: area } = useArea(areaId)
  const needed = LAYERS.some((l) => visible[l.id] && 'usesShadeTime' in l && l.usesShadeTime)
  if (!needed || !area) return null

  return (
    <div className="flex items-center gap-3 rounded-lg border bg-background/95 px-3 py-2 shadow-sm">
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Sun className="size-3.5" aria-hidden />
        Shade on {formatReferenceDate(area.referenceDate)} at
      </span>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        spacing={0}
        value={shadeTime}
        onValueChange={(v) => v && setShadeTime(v as ShadeTime)}
        aria-label="Shade time"
      >
        {area.shadeTimes.map((t) => (
          <ToggleGroupItem key={t} value={t} className="px-3 tabular-nums">
            {formatShadeTime(t)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
