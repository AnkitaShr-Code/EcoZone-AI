import { Layers } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Switch } from '@/components/ui/switch'
import { useUiStore } from '@/state/uiStore'
import { LAYER_GROUPS, LAYERS } from './layerRegistry'

/** Layer toggles, grouped, generated from the registry (UI_RULES.md §4). */
export function LayersControl() {
  const visible = useUiStore((s) => s.visibleLayers)
  const setLayerVisible = useUiStore((s) => s.setLayerVisible)
  const onCount = LAYERS.filter((l) => visible[l.id]).length

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="bg-background shadow-sm">
          <Layers className="size-4" aria-hidden />
          Layers
          <span className="text-muted-foreground tabular-nums">{onCount}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        {LAYER_GROUPS.map((group) => {
          const layers = LAYERS.filter((l) => l.group === group.id)
          if (!layers.length) return null
          return (
            <div key={group.id} className="border-b p-3 last:border-b-0">
              <h3 className="mb-2 text-xs font-semibold text-muted-foreground">{group.label}</h3>
              <ul className="space-y-2.5">
                {layers.map((layer) => (
                  <li key={layer.id} className="flex items-start gap-3">
                    <Switch
                      id={`layer-${layer.id}`}
                      checked={visible[layer.id]}
                      onCheckedChange={(on) => setLayerVisible(layer.id, on)}
                      className="mt-0.5"
                    />
                    <label htmlFor={`layer-${layer.id}`} className="cursor-pointer text-sm leading-tight">
                      {layer.label}
                      <span className="block text-xs text-muted-foreground">{layer.description}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </PopoverContent>
    </Popover>
  )
}
