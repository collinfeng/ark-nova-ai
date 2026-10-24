import { ArrowUpCircle, Award, GraduationCap, Landmark, Layers, Shield, Star, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

/** The one mark for each resource, used by the player panel, the feed and costs, so they all match. */
const RESOURCES: Record<string, { icon: (cls: string) => ReactNode; label: () => string }> = {
  money: { icon: (c) => <MoneyMark className={c} />, label: () => t('playerPanel.money', 'Money') },
  appeal: { icon: (c) => <Star className={cn(c, 'fill-amber-400 text-amber-500')} />, label: () => t('playerPanel.appeal', 'Appeal') },
  conservation: { icon: (c) => <Shield className={cn(c, 'fill-emerald-100 text-emerald-600')} />, label: () => t('playerPanel.conservation', 'Conservation') },
  reputation: { icon: (c) => <Award className={cn(c, 'text-sky-600')} />, label: () => t('playerPanel.reputation', 'Reputation') },
  xtoken: { icon: (c) => <XTokenMark className={c} />, label: () => t('playerPanel.xtokens', 'X-tokens') },
  worker: { icon: (c) => <Users className={cn(c, 'text-slate-600')} />, label: () => t('options.worker', 'Worker') },
  card: { icon: (c) => <Layers className={cn(c, 'text-slate-600')} />, label: () => t('options.card', 'Card') },
  partner_zoo: { icon: (c) => <Landmark className={cn(c, 'text-slate-500')} />, label: () => t('tracks.partnerZoos', 'Partner zoos') },
  university: { icon: (c) => <GraduationCap className={cn(c, 'text-teal-600')} />, label: () => t('tracks.universities', 'Universities') },
  upgrade: { icon: (c) => <ArrowUpCircle className={cn(c, 'text-sky-600')} />, label: () => t('options.upgrade', 'Upgrade') },
}

/** Money's colour: the grey of a card's printed cost, used for every amount of money. */
export const MONEY_BG = '#5f6368'

/** Money as an icon: a grey square with a $. */
export function MoneyMark({ className }: { className?: string }) {
  return <span className={cn('inline-grid place-items-center rounded-[4px] text-[9px] leading-none font-black text-white', className)} style={{ background: MONEY_BG }}>$</span>
}

/** An amount of money as a grey chip, like a card's cost: "$8", or "−$2" for money you pay. */
export function MoneyChip({ n, minus = false, className }: { n: ReactNode; minus?: boolean; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-px rounded-md px-1 py-0.5 text-[11px] leading-none font-extrabold text-white tabular-nums', className)} style={{ background: MONEY_BG }} title={t('playerPanel.money', 'Money')}>
      {minus && '−'}
      <span className="text-[0.75em] font-bold text-white/75">$</span>
      {n}
    </span>
  )
}

/** The X-token as printed: a dark hexagon with an X (the same as in card text and on the tracks). */
export function XTokenMark({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-grid place-items-center bg-slate-700 text-[9px] leading-none font-black text-white', className)}
      style={{ clipPath: 'polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)' }}
    >
      X
    </span>
  )
}

export function isResource(kind: string) {
  return kind in RESOURCES
}

/** A resource's icon (null for an unknown kind). */
export function ResourceIcon({ kind, className = 'size-3.5' }: { kind: string; className?: string }) {
  const r = RESOURCES[kind]
  return r ? <>{r.icon(cn('shrink-0', className))}</> : null
}

/** Icon and number together, centred on one line: "(coin) 12". */
export function Amount({ kind, n, className }: { kind: string; n: ReactNode; className?: string }) {
  if (kind === 'money') return <MoneyChip n={n} className={className} />
  return (
    <span className={cn('inline-flex items-center gap-0.5 leading-none tabular-nums', className)} title={RESOURCES[kind]?.label()}>
      <ResourceIcon kind={kind} />
      {n}
    </span>
  )
}
