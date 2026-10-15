import type { BuildingDesign } from '@/api/types'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'

interface Field {
  key: keyof BuildingDesign
  label: string
  min: number
  max: (d: BuildingDesign) => number
  step: number
  format: (v: number) => string
}

const FIELDS: Field[] = [
  { key: 'floors', label: 'Height', min: 1, max: () => 20, step: 1, format: (v) => `${v} floors` },
  { key: 'footprintPct', label: 'Footprint', min: 10, max: (d) => 100 - d.greenPct, step: 5, format: (v) => `${v}% of plot` },
  { key: 'greenPct', label: 'Green or open space', min: 0, max: (d) => 100 - d.footprintPct, step: 5, format: (v) => `${v}% of plot` },
  { key: 'orientationDeg', label: 'Orientation of the long side', min: 0, max: () => 165, step: 15, format: (v) => `${v}° from north` },
]

/** The four proposal inputs. Each change rescores instantly (ARCHITECTURE.md rule 1). */
export function DesignSliders({ design, onChange }: { design: BuildingDesign; onChange: (patch: Partial<BuildingDesign>) => void }) {
  return (
    <div className="space-y-4">
      {FIELDS.map((f) => (
        <div key={f.key} className="space-y-2">
          <div className="flex items-baseline justify-between">
            <Label htmlFor={`design-${f.key}`}>{f.label}</Label>
            <span className="text-sm tabular-nums">{f.format(design[f.key])}</span>
          </div>
          <Slider
            id={`design-${f.key}`}
            min={f.min}
            max={f.max(design)}
            step={f.step}
            value={[design[f.key]]}
            onValueChange={([v]) => onChange({ [f.key]: v })}
            aria-label={f.label}
          />
        </div>
      ))}
    </div>
  )
}
