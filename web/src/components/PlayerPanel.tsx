import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Hammer,
  Hand,
  Handshake,
  Landmark,
  Layers,
  PawPrint,
  type LucideIcon,
} from 'lucide-react'
import type { ActionName, Board, Card, Player, Slot } from '@/api/types'
import { ResourceIcon } from './Resource'
import { ActionTokens, effectiveStrength } from './ActionTokens'
import { ACTION_HEX, CONTINENTS, ICON_META, ICON_ORDER } from '@/lib/game'
import { t, term } from '@/i18n'
import { cn } from '@/lib/utils'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ActionRuleInfo } from './ActionRuleInfo'
import { CardChip } from './CardTile'
import { IconDot } from './Rich'

const ACTION_ICON: Record<ActionName, LucideIcon> = {
  animals: PawPrint,
  build: Hammer,
  cards: Layers,
  association: Handshake,
  sponsors: Landmark,
}

function Stat({ icon, label, children, className }: { icon: React.ReactNode; label: string; children: React.ReactNode; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<div />} className={cn('flex items-center gap-1 rounded-md bg-muted/60 px-1.5 py-1 text-[13px] leading-none font-semibold tabular-nums', className)}>
        {icon}
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

export function ActionIcon({ slot, slots, active }: { slot: Slot; slots: Slot[]; active: boolean }) {
  const Icon = ACTION_ICON[slot.action]
  const off = active && slot.playable === false
  const tile = (
    <div
      className={cn(
        'relative flex aspect-square flex-col items-center justify-center rounded-lg text-white',
        slot.upgraded ? 'border-2 border-yellow-400 shadow-[0_0_0_1px_rgba(250,204,21,0.5)]' : 'border-2 border-transparent',
        off && 'opacity-35 grayscale',
      )}
      style={{ background: ACTION_HEX[slot.action] }}
    >
      <Icon className="size-4" strokeWidth={2.3} />
      <span className="text-[15px] leading-none font-extrabold tabular-nums">{effectiveStrength(slot)}</span>
      {slot.upgraded && <span className="absolute -top-1.5 -right-1.5 rounded bg-yellow-400 px-0.5 text-[8px] leading-tight font-black text-black">II</span>}
      <ActionTokens slot={slot} className="absolute inset-x-0 -bottom-1.5 justify-center" />
    </div>
  )
  return (
    <HoverCard>
      <HoverCardTrigger render={<div />}>{tile}</HoverCardTrigger>
      <HoverCardContent side="top" align="start" className="w-[30rem] max-w-[calc(100vw-2rem)] p-0">
        <ActionRuleInfo action={slot.action} strength={effectiveStrength(slot)} upgraded={slot.upgraded} reason={off ? slot.reason : undefined} slot={slot} slots={slots} />
      </HoverCardContent>
    </HoverCard>
  )
}

export function PlayerPanel({ p, board, name, active }: { p: Player; board: Board; name: string; active: boolean }) {
  const [open, setOpen] = useState(false)
  const you = p.you
  const opp = board.players.find((q) => q.idx !== p.idx)
  const turn = board.decision?.player === p.idx
  const zoo: Card[] = p.zoo_cards
  const known: Card[] = p.known_hand ?? []
  return (
    <section className={cn('rounded-xl border bg-white p-2.5 shadow-xs', you ? 'border-l-4 border-l-sky-500' : 'border-l-4 border-l-orange-500', turn && 'ring-2 ring-emerald-400/70')}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className={cn('text-[11px] font-bold tracking-wide uppercase', you ? 'text-sky-700' : 'text-orange-700')}>{you ? t('playerPanel.you', 'You') : t('playerPanel.ai', 'AI')}</div>
          <div className="truncate text-[11px] text-muted-foreground" title={name}>
            {you ? t('playerPanel.human', 'human') : name}
          </div>
          {turn && (
            <div className="mt-0.5 flex items-center gap-1 text-[10px] font-semibold text-emerald-700">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
              </span>
              {you ? t('playerPanel.yourTurnLower', 'your turn') : t('playerPanel.toMove', 'to move')}
            </div>
          )}
        </div>
        <Tooltip>
          <TooltipTrigger render={<div />} className="text-right">
            <div className="text-2xl leading-none font-extrabold tabular-nums">{p.points}</div>
            <div className="text-[10px] leading-tight text-muted-foreground">{p.points < 0 ? t('playerPanel.markersCrossIn', 'Markers cross in {count}', { count: -p.points }) : t('playerPanel.markersCrossed', 'Markers crossed')}</div>
            {you && opp && (
              <div className="text-[10px] leading-tight font-medium text-muted-foreground tabular-nums">
                {t('playerPanel.versusAi', 'vs AI: {delta}', { delta: `${p.points - opp.points > 0 ? '+' : ''}${p.points - opp.points}` })}
              </div>
            )}
          </TooltipTrigger>
          <TooltipContent>{t('playerPanel.pointsTooltip', "Points = appeal minus the appeal value your conservation marker points at; the game ends when a player's markers cross.")}</TooltipContent>
        </Tooltip>
      </div>

      <div className="mt-2 grid grid-cols-4 gap-1">
        <Stat icon={<ResourceIcon kind="appeal" />} label={t('playerPanel.appeal', 'Appeal')}>{p.appeal}</Stat>
        <Stat icon={<ResourceIcon kind="conservation" />} label={t('playerPanel.conservation', 'Conservation')}>{p.conservation}</Stat>
        <Stat icon={<ResourceIcon kind="reputation" />} label={t('playerPanel.reputation', 'Reputation')}>{p.reputation}</Stat>
        <Stat icon={<ResourceIcon kind="money" />} label={t('playerPanel.moneyIncome', 'Money {money}, income +{income} per break', { money: p.money, income: p.income })}>
          {p.money}
          <span className="text-[10px] font-medium text-emerald-700">+{p.income}</span>
        </Stat>
        <Stat icon={<ResourceIcon kind="xtoken" />} label={t('playerPanel.xtokens', 'X-tokens')}>{p.xtokens}</Stat>
        <Stat icon={<ResourceIcon kind="worker" />} label={t('playerPanel.workers', 'Workers: active / total')}>
          {p.active_workers}/{p.workers}
        </Stat>
        <Stat icon={<Hand className="size-3.5 text-slate-500" />} label={t('playerPanel.handSize', 'Cards in hand / hand limit')}>
          {p.hand_size}/{p.hand_limit}
        </Stat>
        <Stat icon={<Handshake className="size-3.5 text-violet-500" />} label={t('playerPanel.projectsSupported', 'Conservation projects supported')}>{p.projects_supported}</Stat>
      </div>

      <div className="mt-1 grid grid-cols-[1fr_auto] items-center gap-1">
        <Stat icon={<ResourceIcon kind="partner_zoo" />} label={t('playerPanel.partnerZoos', 'Partner zoos: {list}', { list: p.partner_zoos.map((c) => ICON_META[c]?.label ?? c).join(t('common.listSep', ', ')) || t('common.none', 'none') })} className="font-medium">
          <span className="flex items-center gap-0.5">
            {CONTINENTS.map((c) => {
              const has = p.partner_zoos.includes(c)
              return <span key={c} className={cn('size-3 rounded-full', !has && 'opacity-20')} style={{ background: ICON_META[c].color }} />
            })}
          </span>
        </Stat>
        <Stat icon={<ResourceIcon kind="university" />} label={t('playerPanel.universities', 'Universities: {list}', { list: p.universities.map((u) => term('universities', u, u)).join(t('common.listSep', ', ')) || t('common.none', 'none') })}>
          {p.universities.length}
        </Stat>
      </div>

      <div className="mx-auto mt-2 grid max-w-80 grid-cols-5 gap-1.5">
        {p.slots.map((s, i) => (
          <ActionIcon key={`${s.action}-${i}`} slot={s} slots={p.slots} active={active} />
        ))}
      </div>

      <div className="mx-auto mt-2 grid max-w-80 grid-cols-5 gap-x-1 gap-y-1.5">
        {ICON_ORDER.map((k) => {
          const n = p.icons[k] ?? 0
          return (
            <Tooltip key={k}>
              <TooltipTrigger render={<div />} className={cn('flex items-center justify-center gap-1', n === 0 && 'opacity-30')}>
                <IconDot name={k} size={20} />
                <span className="w-3 text-[13px] leading-none font-bold tabular-nums">{n}</span>
              </TooltipTrigger>
              <TooltipContent>
                {ICON_META[k].label}: {n}
              </TooltipContent>
            </Tooltip>
          )
        })}
      </div>

      <button type="button" className="mt-2 flex w-full items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground" onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        {t('playerPanel.zooCards', 'Zoo cards ({count})', { count: zoo.length })}
        {!you && known.length > 0 ? t('playerPanel.seenInHandJoined', ' / {count} seen in hand', { count: known.length }) : ''}
      </button>
      {open && (
        <div className="mt-1 max-h-32 space-y-1 overflow-y-auto">
          <div className="flex flex-wrap gap-1">
            {zoo.length === 0 && <span className="text-[11px] text-muted-foreground">{t('playerPanel.noCardsPlayed', 'no cards played yet')}</span>}
            {zoo.map((c) => (
              <CardChip key={c.id} id={c.id} card={c} />
            ))}
          </div>
          {!you && known.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground">{t('playerPanel.cardsSeenTaken', 'Cards you saw it take (may be played already)')}</div>
              <div className="flex flex-wrap gap-1">
                {known.map((c) => (
                  <CardChip key={c.id} id={c.id} card={c} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
