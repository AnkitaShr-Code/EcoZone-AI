import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { LayersControl } from '@/map/LayersControl'
import { Legend } from '@/map/Legend'
import { MapView } from '@/map/MapView'
import { ScenarioToggle } from '@/map/ScenarioToggle'
import { TimeControl } from '@/map/TimeControl'
import { TopBar } from '@/shell/TopBar'
import { WorkflowPanel } from '@/shell/WorkflowPanel'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

/** Fixed layout regions (UI_RULES.md §2). */
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <div className="flex h-full flex-col">
          <TopBar />
          <div className="flex min-h-0 flex-1 max-lg:flex-col">
            <WorkflowPanel />
            <main className="relative min-h-0 flex-1">
              <MapView />
              <div className="absolute top-3 right-3 z-10">
                <LayersControl />
              </div>
              <div className="absolute bottom-8 left-3 z-10 flex flex-wrap items-center gap-2">
                <ScenarioToggle />
                <TimeControl />
              </div>
              <div className="absolute right-3 bottom-8 z-10">
                <Legend />
              </div>
            </main>
          </div>
        </div>
        <Toaster theme="light" position="bottom-left" />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
