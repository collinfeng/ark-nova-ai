import { Hourglass } from 'lucide-react'
import type { Player } from '@/api/types'
import { t } from '@/i18n'
import { CardTile } from './CardTile'

export function HandRow({ me, finalOnly = false }: { me: Player; finalOnly?: boolean }) {
  const hand = me.hand ?? []
  const fin = me.final_cards ?? []
  return (
    <section className="flex min-h-0 flex-col rounded-xl border bg-white px-3 pt-1 pb-1 shadow-xs">
      <div className="mb-1 flex items-baseline gap-2 text-xs">
        <h2 className="text-sm font-semibold">{finalOnly ? t('hand.finalTitle', 'Final scoring cards') : t('hand.title', 'Your hand')}</h2>
        {!finalOnly && (
          <span className="text-muted-foreground">
            {hand.length}/{me.hand_limit}
          </span>
        )}
        {fin.length > 0 && (
          <span className="ml-auto flex items-center gap-1 text-muted-foreground">
            <Hourglass className="size-3" /> {t('hand.finalCardsPrivate', 'final scoring cards, only you see them')}
          </span>
        )}
      </div>
      <div className="scroll-area flex min-h-0 items-start gap-2 overflow-x-auto overflow-y-hidden pt-0.5 pb-1">
        {!finalOnly && hand.length === 0 && <div className="py-6 text-xs text-muted-foreground">{t('hand.empty', 'empty hand')}</div>}
        {!finalOnly && hand.map((c) => (
          <CardTile key={c.id} card={c} />
        ))}
        {!finalOnly && fin.length > 0 && <div className="mx-1 w-px shrink-0 self-stretch bg-border" />}
        {fin.map((c) => (
          <CardTile key={c.id} card={c} />
        ))}
      </div>
    </section>
  )
}
