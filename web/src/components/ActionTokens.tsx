import { Skull } from 'lucide-react'
import type { Slot } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

export type ActionToken = 'multiplier' | 'venom' | 'constriction'

/** What Constriction takes off a card's strength (engine: CONSTRICTION_PENALTY). */
export const CONSTRICTION = 2
/** What using a card without Venom costs while another card has it (engine: VENOM_COST). */
export const VENOM_COST = 2

function tokensOf(slot: Slot): ActionToken[] {
  return slot.tokens.filter((x): x is ActionToken => x === 'multiplier' || x === 'venom' || x === 'constriction')
}

/** The strength a card is used at now: its slot, less 2 under Constriction. */
export function effectiveStrength(slot: Slot) {
  return slot.strength - (tokensOf(slot).includes('constriction') ? CONSTRICTION : 0)
}

/** Using this card costs money: you hold Venom on another card but not on this one. */
export function venomCost(slot: Slot, slots: Slot[]) {
  return !tokensOf(slot).includes('venom') && slots.some((s) => tokensOf(s).includes('venom'))
}

const STYLE: Record<ActionToken, { bg: string; label: () => string }> = {
  multiplier: { bg: '#a16207', label: () => t('actionTokens.multiplier', 'x2 token') },
  venom: { bg: '#4d7c0f', label: () => t('actionTokens.venom', 'Venom') },
  constriction: { bg: '#be123c', label: () => t('actionTokens.constriction', 'Constriction') },
}

/** One chip per token on an action card: "2×" for the multiplier, a skull for Venom, "−2" for Constriction. */
export function ActionTokens({ slot, className }: { slot: Slot; className?: string }) {
  const tokens = tokensOf(slot)
  if (tokens.length === 0) return null
  return (
    <span className={cn('inline-flex items-center gap-px', className)}>
      {tokens.map((k, i) => (
        <span
          key={i}
          title={STYLE[k].label()}
          className="inline-flex h-3.5 items-center rounded-full px-1 text-[9px] leading-none font-black text-white ring-1 ring-white"
          style={{ background: STYLE[k].bg }}
        >
          {k === 'multiplier' ? '2×' : k === 'venom' ? <Skull className="size-2.5" strokeWidth={2.6} /> : `−${CONSTRICTION}`}
        </span>
      ))}
    </span>
  )
}

/** The rules of the tokens on this card, for the action card's hover. */
export function TokenRules({ slot, slots }: { slot: Slot; slots: Slot[] }) {
  const tokens = [...new Set(tokensOf(slot))]
  const pay = venomCost(slot, slots)
  if (tokens.length === 0 && !pay) return null
  const text: Record<ActionToken, string> = {
    multiplier: t('actionTokens.multiplierRule', 'x2 token: after this action you may carry it out once more at the same strength. The token is then used up.'),
    venom: t('actionTokens.venomRule', 'Venom: while any of your action cards has a Venom token, using a card without one costs {cost} money. Using this card removes its token.', { cost: VENOM_COST }),
    constriction: t('actionTokens.constrictionRule', 'Constriction: this card is {n} weaker (strength {strength} now). Using it removes the token.', { n: CONSTRICTION, strength: effectiveStrength(slot) }),
  }
  return (
    <div className="space-y-1.5">
      {tokens.map((k) => (
        <p key={k} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700">
          <ActionTokens slot={{ ...slot, tokens: [k] }} className="mt-0.5 shrink-0" />
          <span>{text[k]}</span>
        </p>
      ))}
      {pay && (
        <p className="rounded-lg border border-lime-200 bg-lime-50 px-3 py-2 text-xs leading-relaxed text-lime-900">
          {t('actionTokens.venomCost', 'Venom is on another of your cards, so using this one costs {cost} money.', { cost: VENOM_COST })}
        </p>
      )}
    </div>
  )
}
