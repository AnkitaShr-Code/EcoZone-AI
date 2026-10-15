import { ProtectWorkflow } from '@/features/protect/ProtectWorkflow'
import { RepairWorkflow } from '@/features/repair/RepairWorkflow'
import { useUiStore } from '@/state/uiStore'
import { SelectionCard } from './SelectionCard'

export function WorkflowPanel() {
  const mode = useUiStore((s) => s.mode)
  return (
    <aside className="flex w-[380px] shrink-0 flex-col border-r bg-muted/20 max-lg:h-[45%] max-lg:w-full max-lg:border-r-0 max-lg:border-b">
      {/* relative: keeps absolutely positioned sr-only labels inside the scroll area */}
      <div className="relative flex-1 space-y-3 overflow-y-auto p-3">
        <SelectionCard />
        {mode === 'repair' ? <RepairWorkflow /> : <ProtectWorkflow />}
      </div>
    </aside>
  )
}
