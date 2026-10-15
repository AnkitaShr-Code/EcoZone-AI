import { useEffect, useMemo } from 'react'
import { FileText } from 'lucide-react'
import { buildingChange } from '@/api/changes'
import { useArea, useExplain, useLayer } from '@/api/hooks'
import { changesKey } from '@/api/keys'
import { EmptyState } from '@/components/EmptyState'
import { StepCard } from '@/components/StepCard'
import { formatCount, formatDesign } from '@/lib/format'
import { distanceM } from '@/lib/geo'
import { useScenarioStore } from '@/state/scenarioStore'
import { useScenario } from '@/state/useScenario'
import { useSteps } from '@/state/useSteps'
import { useUiStore } from '@/state/uiStore'
import { BuildoutStepContent } from './BuildoutStepContent'
import { DesignsStepContent } from './DesignsStepContent'
import { ParcelStepContent } from './ParcelStepContent'
import { ProposalStepContent } from './ProposalStepContent'
import { ProtectBrief } from './ProtectBrief'
import { useProtectStore } from './protectStore'
import { useProtectSearch } from './useProtectSearch'

const BUILDOUT_STEP = 3

/** Protect: parcel → proposal → compare designs → build-out → brief (UI_RULES.md §3). */
export function ProtectWorkflow() {
  const { areaId, unitCosts, result } = useScenario()
  const selection = useUiStore((s) => s.selection)
  const openStep = useUiStore((s) => s.openStep.protect)
  const { data: area } = useArea(areaId)
  const { data: parcels } = useLayer(areaId, 'parcels')
  const store = useProtectStore()
  const { parcelId, design, chosen, buildout } = store
  const setChanges = useScenarioStore((s) => s.setChanges)
  const search = useProtectSearch()
  const explain = useExplain(areaId)
  const { stateOf, edit, advance } = useSteps('protect')

  const parcel = parcels?.features.find((f) => f.properties.id === parcelId)?.properties
  const inRadius = useMemo(() => (parcel && parcels
    ? parcels.features.map((f) => f.properties).filter((p) => distanceM(p.center, parcel.center) <= buildout.radiusM)
    : []), [parcel, parcels, buildout.radiusM])

  // The scenario on the map: the build-out once it has run, otherwise the single proposal.
  const changes = useMemo(() => {
    if (!parcelId || !design) return []
    if (buildout.ran && openStep >= BUILDOUT_STEP) return inRadius.map((p) => buildingChange(p.id, design))
    return [buildingChange(parcelId, design)]
  }, [parcelId, design, buildout.ran, openStep, inRadius])
  const key = changesKey(changes)
  useEffect(() => {
    setChanges('protect', changes)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- key captures the change set
  }, [key, setChanges])

  const explainedKey = explain.variables ? changesKey(explain.variables.changes) : null
  const chooseParcel = () => {
    const p = parcels?.features.find((f) => f.properties.id === selection?.id)?.properties
    if (!p) return
    store.setParcel(p.id, { floors: 12, footprintPct: 60, greenPct: 10, orientationDeg: Math.round(p.streetBearingDeg / 15) * 15 % 180 })
    explain.reset()
    advance()
  }

  return (
    <div className="space-y-3">
      <StepCard
        number={1}
        title="Choose parcel"
        state={stateOf(0)}
        summary={parcel?.name}
        instruction="Pick the vacant parcel the proposed building would go on."
        primary={{ label: 'Use this parcel', onClick: chooseParcel, disabled: selection?.kind !== 'parcel', disabledReason: 'Select a parcel on the map or in the list.' }}
        onEdit={() => edit(0)}
      >
        <ParcelStepContent />
      </StepCard>

      <StepCard
        number={2}
        title="Describe proposal"
        state={stateOf(1)}
        summary={design ? formatDesign(design) : undefined}
        instruction="Set the proposed building. Scores update as you move the sliders."
        lockedReason="Choose a parcel first"
        primary={{ label: 'Find better designs', onClick: () => { store.startSearch(); if (stateOf(1) === 'open') advance() }, disabled: !result }}
        secondary={{ label: 'Explain the impact', onClick: () => unitCosts && explain.mutate({ changes, unitCosts }) }}
        onEdit={() => edit(1)}
      >
        <ProposalStepContent explanation={explain.data} explanationStale={!!explainedKey && explainedKey !== key} />
      </StepCard>

      <StepCard
        number={3}
        title="Compare designs"
        state={stateOf(2)}
        summary={chosen ? `Option ${chosen} chosen` : undefined}
        instruction={search.result ? 'Pick an option to see it on the map, then use it.' : 'Gemini proposes designs; the engine scores each one.'}
        lockedReason="Describe the proposal first"
        primary={{ label: 'Use this design', onClick: advance, disabled: !chosen, disabledReason: search.result ? 'Pick an option.' : 'Wait for the search to finish.' }}
        secondary={search.result ? { label: 'Search again', onClick: store.startSearch } : undefined}
        onEdit={() => edit(2)}
      >
        <DesignsStepContent search={search} />
      </StepCard>

      <StepCard
        number={4}
        title="Check build-out"
        state={stateOf(3)}
        summary={buildout.ran ? `${formatCount(inRadius.length, 'parcel')} within ${buildout.radiusM} m` : 'Skipped'}
        instruction="Optional. See what happens if every vacant parcel nearby is built to the same envelope."
        lockedReason="Optional. Compare designs first"
        primary={buildout.ran
          ? { label: 'Continue to brief', onClick: advance }
          : { label: 'Run build-out', onClick: () => store.setBuildout({ ran: true }) }}
        secondary={buildout.ran ? { label: 'Clear build-out', onClick: () => store.setBuildout({ ran: false }) } : { label: 'Skip build-out', onClick: advance }}
        onEdit={() => edit(3)}
      >
        <BuildoutStepContent parcelsInRadius={inRadius} />
      </StepCard>

      <StepCard
        number={5}
        title="Export brief"
        state={stateOf(4)}
        instruction="Download a printable planning brief comparing the options."
        lockedReason="Choose a design first"
        primary={{ label: 'Download brief', onClick: () => window.print(), disabled: !area }}
      >
        <EmptyState icon={FileText}>The brief compares options A, B and C, records the chosen design and, if run, the build-out.</EmptyState>
        {parcel && <ProtectBrief search={search} parcel={parcel} parcelCount={inRadius.length} />}
      </StepCard>
    </div>
  )
}
