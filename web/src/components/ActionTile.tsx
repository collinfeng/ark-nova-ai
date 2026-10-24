import { Skull, Sparkles } from 'lucide-react'
import { MoneyChip } from './Resource'
import type { Option, Slot } from '@/api/types'
import { ACTIONS, pct } from '@/lib/game'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { ActionRuleInfo } from './ActionRuleInfo'
import { ActionTokens, effectiveStrength, venomCost, VENOM_COST } from './ActionTokens'

interface Props {
  slot: Slot
  /** All of the player's cards (Venom on another card makes this one cost money). */
  slots: Slot[]
  /** The option this tile plays in the current mode (act at the chosen x, or the X-token option). */
  option?: Option
  mode: 'act' | 'xtoken'
  x: number
  /** Why the tile is greyed out. */
  reason?: string
  hints: boolean
  isBest: boolean
  busy: boolean
  onPlay: (index: number) => void
}

export function ActionTile({ slot, slots, option, mode, x, reason, hints, isBest, busy, onPlay }: Props) {
  const meta = ACTIONS[slot.action]
  const playable = !!option
  const spend = mode === 'xtoken'
  const strength = effectiveStrength(slot) + x
  const pay = venomCost(slot, slots)
  return (
    <HoverCard>
      <HoverCardTrigger
        render={<button type="button" />}
        aria-disabled={busy || !playable}
        tabIndex={busy ? -1 : 0}
        onClick={() => !busy && playable && option && onPlay(option.index)}
        className={cn(
          'relative flex min-h-[3rem] items-center gap-2 rounded-xl border-2 px-2 py-1.5 text-left transition outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
          playable ? cn(meta.tint, 'hover:-translate-y-0.5 hover:shadow-md', spend && 'border-dashed') : 'cursor-not-allowed border-dashed border-border bg-muted/60 opacity-60 grayscale',
          isBest && hints && 'ring-2 ring-sky-500',
        )}
      >
        <span className={cn('relative flex size-8 shrink-0 items-center justify-center rounded-lg text-lg font-bold text-white tabular-nums', meta.color, spend && 'opacity-60')}>
          {spend ? '+X' : strength}
          <ActionTokens slot={slot} className="absolute inset-x-[-6px] -bottom-2 justify-center" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 text-sm leading-tight font-semibold">
            {spend ? t('decision.xTokenWith', 'X-token with {action}', { action: meta.label }) : meta.label}
            {slot.upgraded && <span className="rounded bg-yellow-400 px-1 text-[10px] leading-tight font-black text-black">II</span>}
          </div>
          {!playable && reason ? (
            <div className="line-clamp-2 text-[10px] leading-tight text-rose-700">{reason}</div>
          ) : (
            (hints || pay) && (
              <div className="flex items-center gap-1 text-[10px] text-sky-800 tabular-nums">
                {hints && isBest && <Sparkles className="size-3" />}
                {hints && pct(option?.ai_prob)}
                {pay && (
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-lime-100 px-1 font-bold text-lime-900" title={t('actionTokens.venomCost', 'Venom is on another of your cards, so using this one costs {cost} money.', { cost: VENOM_COST })}>
                    <Skull className="size-3 text-lime-700" /><MoneyChip n={VENOM_COST} minus className="text-[9px]" />
                  </span>
                )}
              </div>
            )
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="top" align="start" className="w-[30rem] max-w-[calc(100vw-2rem)] p-0">
        <ActionRuleInfo
          action={slot.action}
          strength={strength}
          upgraded={slot.upgraded}
          xToken={spend}
          reason={!playable ? reason : undefined}
          slot={slot}
          slots={slots}
        />
      </HoverCardContent>
    </HoverCard>
  )
}
