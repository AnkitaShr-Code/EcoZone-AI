import type { DesignOption, ParcelProps } from '@/api/types'
import { BriefSection, BriefSheet } from '@/components/BriefSheet'
import { formatDesign, formatScore } from '@/lib/format'
import { useScenario } from '@/state/useScenario'
import { useProtectStore } from './protectStore'
import type { ProtectSearch } from './useProtectSearch'

const RISK_WORD = { LOW: 'Low', MODERATE: 'Moderate', HIGH: 'High' } as const

/** The printable planning brief: options compared, the planner's choice, and the build-out. */
export function ProtectBrief({ search, parcel, parcelCount }: { search: ProtectSearch; parcel: ParcelProps; parcelCount: number }) {
  const { result } = useScenario()
  const { chosen, buildout } = useProtectStore()
  const options = search.result?.options ?? []
  const choice = options.find((o) => o.key === chosen)

  return (
    <BriefSheet title={`Planning brief: ${parcel.name}`} subtitle={`${parcel.areaM2.toLocaleString('en-IN')} m² plot on a ${parcel.roadWidthM} m street`}>
      <BriefSection title="Options compared">
        <table className="w-full text-left">
          <thead><tr className="border-b"><th className="py-1">Option</th><th>Design</th><th>Worst change</th><th>Risk</th><th>Floor area kept</th></tr></thead>
          <tbody>
            {options.map((o: DesignOption) => (
              <tr key={o.key} className="border-b">
                <td className="py-1">{o.key} · {o.title}</td>
                <td>{formatDesign(o.design)}</td>
                <td>{formatScore(o.candidate.score)}</td>
                <td>{o.candidate.risk ? RISK_WORD[o.candidate.risk.label] : ''}</td>
                <td>{o.candidate.floorAreaPct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        {search.result && <p>{search.result.explanation.paragraphs.join(' ')}</p>}
      </BriefSection>

      {choice && (
        <BriefSection title="Planner's choice">
          <p>Option {choice.key} ({choice.title.toLowerCase()}): {formatDesign(choice.design)}. {choice.tradeOff}</p>
        </BriefSection>
      )}

      {buildout.ran && result && (
        <BriefSection title={`Build-out: ${parcelCount} vacant parcels within ${buildout.radiusM} m`}>
          <p>
            Area cooling score {formatScore(result.before.acs)} today, {formatScore(result.after.acs)} built out; ventilation {formatScore(result.before.vci)} to {formatScore(result.after.vci)}.
            {' '}{result.blocksWorse} existing blocks lose cooling score.
          </p>
        </BriefSection>
      )}
    </BriefSheet>
  )
}
