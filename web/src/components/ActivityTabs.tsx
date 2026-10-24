import { Bot, ChartNoAxesCombined, ScrollText } from 'lucide-react'
import type { Board } from '@/api/types'
import { t } from '@/i18n'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AiPlayedBox, AiTurnDetails, AnalysisPanel, LogPanel } from './AnalysisPanel'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { useSettings } from '@/lib/settings'

/** The activity rail under the player panels. The robot is the default view. */
export function ActivityTabs({
  board,
  handedOver,
  canHint,
}: {
  board: Board
  handedOver: boolean
  canHint: boolean
}) {
  const { activityPreview } = useSettings()
  return (
    <Tabs defaultValue="activity" className="gap-0 rounded-xl border bg-white shadow-xs">
      <div className="sticky top-0 z-10 rounded-t-xl bg-white p-1.5 pb-0">
        <TabsList className="w-full">
          <HoverCard key={String(activityPreview)} open={activityPreview ? undefined : false}>
            <HoverCardTrigger delay={250} closeDelay={200} render={<TabsTrigger value="activity" className="data-active:bg-orange-50 data-active:text-orange-900" />}>
              <Bot />
              {t('tabs.activity', 'Activity')}
            </HoverCardTrigger>
            <HoverCardContent side="right" align="start" className="w-[300px] max-w-[calc(100vw-2rem)] p-0">
              <AiTurnDetails board={board} />
            </HoverCardContent>
          </HoverCard>
          {canHint && (
            <TabsTrigger value="analysis">
              <ChartNoAxesCombined />
              {t('tabs.analysis', 'AI analysis')}
            </TabsTrigger>
          )}
          <TabsTrigger value="log">
            <ScrollText />
            {t('tabs.log', 'Log')}
          </TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="activity">
        <AiPlayedBox board={board} handedOver={handedOver} />
      </TabsContent>
      {canHint && (
        <TabsContent value="analysis">
          <AnalysisPanel board={board} />
        </TabsContent>
      )}
      <TabsContent value="log">
        <LogPanel board={board} />
      </TabsContent>
    </Tabs>
  )
}
