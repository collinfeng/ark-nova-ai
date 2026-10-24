import type { CSSProperties, ReactNode } from 'react'
import { ChevronsLeft, CircleHelp, Gift, GraduationCap, Handshake, Landmark, Layers, Lock, Repeat, Store, Trash2, Users, Warehouse } from 'lucide-react'
import type { Board, Player, TaskName, TrackEffect, Tracks } from '@/api/types'
import { cn } from '@/lib/utils'
import { GameIcon } from './GameIcon'
import { t } from '@/i18n'
import { ICON_META } from '@/lib/game'
import { UniversityChip } from './Glyphs'
import { TokenChip } from './Rich'
import { ResourceIcon } from './Resource'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** A reward stop on a numbered track, as one player sees it. */
interface Stop {
  at: number
  /** Short words for the chip, e.g. "1 card". */
  short: ReactNode
  /** Full text for the hover. */
  tip: ReactNode
  /** Out of reach until an upgrade (reputation past 9 without Cards II). */
  locked?: boolean
  /** Shared reward already gone (the final-card discard). */
  spent?: boolean
  claimed?: boolean
  youClaimed?: boolean
  aiClaimed?: boolean
  aiLocked?: boolean
  specificClaims?: boolean
}

const YOU = 'bg-sky-500'
const AI = 'bg-orange-500'

function ClaimDots({ you, ai }: { you?: boolean; ai?: boolean }) {
  if (!you && !ai) return null
  return <span className="flex h-3.5 shrink-0 flex-col justify-between" aria-hidden="true"><i className={cn('size-1 rounded-full', you ? YOU : 'bg-transparent')} /><i className={cn('size-1 rounded-full', ai ? AI : 'bg-transparent')} /></span>
}

/** Keep ownership on the actual choice, outside its disabled/grey appearance. */
function ClaimedReward({ by = [], you, ai, children }: { by?: number[]; you: number; ai: number; children: ReactNode }) {
  return <span className="relative inline-flex py-1">
    {children}
    {by.includes(you) && <i aria-label={t('tracks.youLabel', 'You')} className={cn('absolute left-1/2 top-0 size-1.5 -translate-x-1/2 rounded-full ring-1 ring-white', YOU)} />}
    {by.includes(ai) && <i aria-label="AI" className={cn('absolute bottom-0 left-1/2 size-1.5 -translate-x-1/2 rounded-full ring-1 ring-white', AI)} />}
  </span>
}

export function Tip({ tip, children, className, style, side = 'left' }: { tip: ReactNode; children: ReactNode; className?: string; style?: CSSProperties; side?: 'left' | 'top' | 'bottom' | 'right' }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<span />} tabIndex={0} className={className} style={style}>
        {children}
      </TooltipTrigger>
      <TooltipContent side={side} tone="light" className="max-w-72 flex-col items-start gap-2 text-left leading-relaxed">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}

/** The same resource badges as the cards; other rewards use their printed shape. */
export function Reward({ kind, amount = 1 }: { kind: string; amount?: number }) {
  const resources: Record<string, string> = { money: 'Money', conservation: 'ConservationPoint', reputation: 'Reputation', appeal: 'Appeal', xtoken: 'XToken', multiplier: 'MultiplierToken' }
  if (resources[kind]) return <span className="inline-flex items-center text-[15px]"><TokenChip name={resources[kind]} value={String(kind === 'multiplier' ? 2 : amount)} /></span>
  if (kind === 'upgrade') return <span className="inline-flex h-6 min-w-6 shrink-0 items-center justify-center rounded-md bg-red-50 px-1 text-[13px] leading-none font-black text-red-700">II</span>
  if (kind === 'enclosure') return <span className="relative grid size-6 place-items-center text-[11px] font-bold text-emerald-900"><svg viewBox="0 0 24 24" className="absolute inset-0 size-full" aria-hidden="true"><path d="M12 1.5 21 6.8v10.4L12 22.5 3 17.2V6.8Z" fill="#dcfce7" stroke="#86b98f" strokeWidth="1.5" /></svg><span className="relative">{amount}</span></span>
  const glyphs: Record<string, ReactNode> = {
    card: <Layers className="size-4" />,
    worker: <Users className="size-4" />,
    university: <GraduationCap className="size-4" />,
    partner_zoo: <Handshake className="size-4" />,
    sponsor_for_money: <Landmark className="size-4" />,
    final_discard: <Trash2 className="size-4" />,
    kiosk: <Store className="size-4" />,
    clever: <ChevronsLeft className="size-4" />,
    special_enclosure: <Warehouse className="size-4" />,
  }
  const tones: Record<string, string> = {
    card: 'bg-sky-100 text-sky-700', worker: 'bg-violet-100 text-violet-700',
    university: 'bg-teal-100 text-teal-700', final_discard: 'bg-rose-100 text-rose-700',
    kiosk: 'bg-orange-100 text-orange-700', clever: 'bg-indigo-100 text-indigo-700', special_enclosure: 'bg-emerald-100 text-emerald-700',
    partner_zoo: 'bg-emerald-100 text-emerald-700', sponsor_for_money: 'bg-rose-100 text-rose-700',
  }
  return <span className={cn('inline-flex h-6 min-w-6 shrink-0 items-center justify-center gap-0.5 rounded-md px-1 text-[11px] font-semibold', tones[kind] ?? 'bg-amber-100 text-amber-700')}>{glyphs[kind] ?? <Gift className="size-4" />}{amount > 1 && amount}</span>
}

export function Rewards({ effects }: { effects: TrackEffect[] }) {
  return <span className="inline-flex flex-wrap items-center justify-center gap-0.5">{effects.map((e, i) => <Reward key={i} kind={e.kind} amount={e.amount} />)}</span>
}

/** Each coloured tile is a concrete reward; taken tiles stay in the legend. */
function BonusTile({ effects, available = true }: { effects: TrackEffect[]; available?: boolean }) {
  const tones: Record<string, string> = {
    money: 'border-slate-300 bg-slate-50', xtoken: 'border-slate-300 bg-slate-50',
    reputation: 'border-blue-200 bg-blue-50', university: 'border-teal-200 bg-teal-50',
    partner_zoo: 'border-emerald-200 bg-emerald-50', enclosure: 'border-green-200 bg-green-50',
    card: 'border-sky-200 bg-sky-50', multiplier: 'border-yellow-300 bg-yellow-50',
    sponsor_for_money: 'border-rose-200 bg-rose-50',
  }
  return <span className={cn('inline-flex min-h-7 items-center justify-center rounded-md border px-1', tones[effects[0]?.kind] ?? 'border-slate-200 bg-slate-50', !available && 'opacity-50 grayscale')}><Rewards effects={effects} /></span>
}

/** Same mark as a card's income: comes back at every break. */
export function RepeatMark() {
  return (
    <span className="grid size-3.5 shrink-0 place-items-center rounded-[3px] border border-purple-800 bg-purple-600 text-white">
      <Repeat className="size-2.5" strokeWidth={3} />
    </span>
  )
}

export function OnceMark() {
  return <span className="grid size-3.5 shrink-0 place-items-center rounded-[3px] border border-amber-500 bg-amber-200 text-[8px] font-black text-amber-950">1×</span>
}

/** A horizontal track 0..max: numbered reward stops, your marker above, the AI's below. */
function Ruler({ max, stops, you, ai, gate }: { max: number; stops: Stop[]; you: number; ai: number; gate?: number }) {
  const left = (v: number) => `${(Math.min(Math.max(v, 0), max) / max) * 100}%`
  return (
    <div className="relative mx-2 h-8">
      <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-slate-200" />
      {Array.from({ length: max + 1 }, (_, v) => (
        <span key={v} className="absolute top-1/2 h-1.5 w-px -translate-x-1/2 -translate-y-1/2 bg-slate-300" style={{ left: left(v) }} />
      ))}
      {gate !== undefined && (
        <Tip
          tip={t('tracks.gateTooltip', 'Reputation stops at {gate} until Cards is upgraded', { gate })}
          className="absolute top-0.5 bottom-0.5 z-10 w-0.5 -translate-x-1/2 rounded bg-red-400"
          style={{ left: left(gate + 0.5) }}
        >
          <span className="block size-full" />
        </Tip>
      )}
      {stops.map((s) => {
        const youDone = s.spent || s.youClaimed
        const aiDone = s.spent || s.aiClaimed
        const youLocked = s.locked && !youDone
        const aiLocked = s.aiLocked && !aiDone
        return (
        <Tip
          key={s.at}
          tip={s.tip}
          className="absolute top-1/2 z-10 -translate-x-1/2 -translate-y-1/2"
          style={{ left: left(s.at) }}
        >
          <span
            className={cn(
              'relative flex size-4 items-center justify-center overflow-hidden rounded-full border text-[9px] leading-none font-bold tabular-nums',
              s.spent || s.claimed ? 'border-slate-300 text-slate-400' : youLocked || aiLocked ? 'border-red-500 text-red-700' : 'border-amber-400 text-amber-900',
              (youLocked || aiLocked) && 'border-dashed',
            )}
          >
            <i className={cn('absolute inset-x-0 top-0 h-1/2', youDone ? 'bg-slate-100' : youLocked ? 'bg-red-100' : 'bg-amber-50')} />
            <i className={cn('absolute inset-x-0 bottom-0 h-1/2', aiDone ? 'bg-slate-100' : aiLocked ? 'bg-red-100' : 'bg-amber-50')} />
            <span className="relative">{s.at}</span>
          </span>
          {s.youClaimed && <i className={cn('absolute -top-1.5 left-1/2 size-1 -translate-x-1/2 rounded-full', YOU)} />}
          {s.aiClaimed && <i className={cn('absolute -bottom-1.5 left-1/2 size-1 -translate-x-1/2 rounded-full', AI)} />}
        </Tip>
      )})}
      <Marker at={left(you)} cls={YOU} top label={t('tracks.youAt', 'You: {n}', { n: you })} />
      <Marker at={left(ai)} cls={AI} label={t('tracks.aiAt', 'AI: {n}', { n: ai })} />
    </div>
  )
}

function Marker({ at, cls, top, label }: { at: string; cls: string; top?: boolean; label: string }) {
  return (
    <span
      title={label}
      className={cn('absolute z-20 size-2.5 -translate-x-1/2 rounded-full ring-2 ring-white', cls, top ? 'top-0' : 'bottom-0')}
      style={{ left: at }}
    />
  )
}

/** Keep the full reward legend visible after either player collects a reward. */
function RewardStops({ stops }: { stops: Stop[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {stops.map((s) => (
        <Tip
          key={s.at}
          tip={s.tip}
          className={cn(
            'inline-flex min-h-8 items-center gap-1.5 rounded-lg border px-1.5 py-1 text-[11px] leading-tight',
            'border-slate-200 bg-white text-slate-700',
            s.locked && 'border-dashed',
          )}
        >
          <span className={cn('inline-flex items-center gap-1.5', !s.specificClaims && (s.claimed || s.spent) && 'opacity-60 grayscale')}><b className="text-[10px] text-slate-500 tabular-nums">{s.at}</b>{s.short}</span>
          {((s.locked && !s.youClaimed) || (s.aiLocked && !s.aiClaimed)) && <Lock className="size-3 text-red-600" />}
          {!s.specificClaims && <ClaimDots you={s.youClaimed} ai={s.aiClaimed} />}
        </Tip>
      ))}
    </div>
  )
}

function Row({ title, icon, you, ai, children, compact = false, tip }: { title: string; icon?: string; you: string; ai: string; children: ReactNode; compact?: boolean; tip?: ReactNode }) {
  const head = <span className="inline-flex items-center gap-1">{icon && <ResourceIcon kind={icon} />}{title}</span>
  return (
    <div className={cn(compact ? 'flex flex-wrap items-center gap-x-2 gap-y-1' : 'space-y-0.5')}>
      <div className={cn('flex items-center text-xs', compact ? 'shrink-0 gap-2' : 'justify-between')}>
        {tip ? <Tip tip={tip} className="font-semibold">{head}</Tip> : <span className="font-semibold">{head}</span>}
        <span className="whitespace-nowrap text-[10px] tabular-nums">
          <span className="font-bold text-sky-700">{you}</span>
          <i className={cn('mx-1 inline-block size-1.5 rounded-full', YOU)} />
          <span className="font-bold text-orange-700">{ai}</span>
          <i className={cn('ml-1 inline-block size-1.5 rounded-full', AI)} />
        </span>
      </div>
      {children}
    </div>
  )
}

function conservationStops(tracks: Tracks, you: number, ai: number): Stop[] {
  return tracks.conservation.stops.map((s) => {
    if (s.kind === 'tile') {
      const choices = s.choices ?? (s.tiles ?? []).map((tile) => ({ ...tile, available: true, claimed_by: [] as number[] }))
      const tileIcon = (tile: typeof choices[number]) => <ClaimedReward by={tile.claimed_by} you={you} ai={ai}><BonusTile effects={tile.effects} available={tile.available} /></ClaimedReward>
      const moneyIcon = <ClaimedReward by={s.money_claimed_by} you={you} ai={ai}><span className={cn('inline-flex', s.money_claimed_by?.includes(you) && s.money_claimed_by.includes(ai) && 'opacity-50 grayscale')}><Reward kind="money" amount={s.money ?? 0} /></span></ClaimedReward>
      const owners = (by: number[] = []) => by.map((idx) => idx === you ? t('tracks.youLabel', 'You') : 'AI').join(' / ')
      return {
        at: s.at,
        specificClaims: true,
        short: <span className="inline-flex flex-wrap items-center gap-1">{choices.map((tile) => <span key={tile.id}>{tileIcon(tile)}</span>)}<span className="text-slate-300">/</span>{moneyIcon}</span>,
        tip: (
          <>
            <div className="font-semibold text-slate-900">{t('tracks.conservationMilestone', 'Conservation {at}', { at: s.at })}</div>
            {choices.map((tile) => <div key={tile.id} className="flex items-center gap-2">{tileIcon(tile)}<span className={cn('text-xs', !tile.available && 'text-slate-400')}>{tile.effects.map((e) => e.label).join(', ')}{!tile.available && ` · ${owners(tile.claimed_by)} ${t('tracks.statusTaken', 'taken')}`}</span></div>)}
            <div className="flex w-full items-center gap-2 border-t border-slate-100 pt-2">{moneyIcon}<span className="text-xs text-slate-500">{t('tracks.moneyAlternative', 'Or take the money instead')}{s.money_claimed_by?.length ? ` · ${owners(s.money_claimed_by)} ${t('tracks.statusTaken', 'taken')}` : ''}</span></div>
          </>
        ),
      }
    }
    const short = s.kind === 'upgrade_or_worker' ? <><Reward kind="upgrade" /><span className="text-slate-300">/</span><Reward kind="worker" /></> : <Reward kind={s.kind} />
    return {
      at: s.at,
      short,
      spent: s.spent,
      tip: t('tracks.conservationStopLabel', 'Conservation {at}: {label}{spent}', { at: s.at, label: s.label, spent: s.spent ? t('tracks.alreadyTaken', ' (already taken by a player)') : '' }),
    }
  })
}

export function TracksPanel({ board }: { board: Board }) {
  const tracks = board.tracks
  const me = board.players.find((p) => p.you)!
  const you = tracks.players.find((p) => p.idx === me.idx)!
  const ai = tracks.players.find((p) => p.idx !== me.idx)!
  const withClaims = (stops: Stop[], yours: number, theirs: number): Stop[] => stops.map((s) => ({
    ...s,
    youClaimed: s.at <= yours,
    aiClaimed: s.at <= theirs,
    claimed: s.at <= Math.min(yours, theirs),
    tip: <>{s.tip}<span className="mt-1 block text-[10px] opacity-75">{t('tracks.claimStatus', 'You: {you} · AI: {ai}', {
      you: yours >= s.at ? t('tracks.statusTaken', 'taken') : s.spent ? t('tracks.unavailable', 'unavailable') : s.locked ? t('tracks.locked', 'locked') : t('tracks.notClaimed', 'not collected'),
      ai: theirs >= s.at ? t('tracks.statusTaken', 'taken') : s.spent ? t('tracks.unavailable', 'unavailable') : s.aiLocked ? t('tracks.locked', 'locked') : t('tracks.notClaimed', 'not collected'),
    })}</span></>,
  }))
  const cons = withClaims(conservationStops(tracks, you.idx, ai.idx), you.conservation, ai.conservation)

  return (
    <section className="space-y-3.5 rounded-xl border bg-white px-3 py-3 shadow-xs" aria-label={t('tracks.title', 'Tracks')}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">{t('tracks.title', 'Tracks')}</h2>
        <span className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <Tip tip={t('tracks.youAbove', 'you (above)')} className="flex items-center gap-1"><i className={cn('size-2 rounded-full', YOU)} />{t('tracks.youLabel', 'You')}</Tip>
          <Tip tip={t('tracks.aiBelow', 'AI (below)')} className="flex items-center gap-1"><i className={cn('size-2 rounded-full', AI)} />AI</Tip>
        </span>
      </div>

      <Row icon="conservation" title={t('tracks.conservation', 'Conservation')} you={String(you.conservation)} ai={String(ai.conservation)}
        tip={t('tracks.conservationTip', 'Conservation points come from supporting projects, donating and some cards. Spaces 2, 5 and 8 give a reward; the first player to reach 10 makes everyone discard a final scoring card. You win when your appeal and conservation markers cross.')}>
        <Ruler max={tracks.conservation.max} stops={cons} you={you.conservation} ai={ai.conservation} />
        <RewardStops stops={cons} />
      </Row>



    </section>
  )
}

/** An association worker: the people icon in a round token, coloured for its player. */
function WorkerIcon({ className }: { className: string }) {
  return (
    <span className={cn('grid size-[18px] shrink-0 place-items-center rounded-full', className)}>
      <Users className="size-3" strokeWidth={2.4} />
    </span>
  )
}

/** What the next use of a task takes, in words, for the hover. */
function nextUse(out: number, next: number | null): string {
  if (out >= 3) return t('assoc.nextBlocked', 'blocked until the break')
  const need = out === 0 ? 1 : 2
  return next === null ? t('assoc.nextNoWorker', 'next use needs {n}, none free', { n: need }) : t('assoc.nextNeeds', 'next use takes {n}', { n: need })
}

/** The workers placed on a task since the break, as on the printed board: blue tokens for you, orange for the
 * AI, side by side; nothing when nobody used it. The hover says what the next use takes for each player. */
function TaskWorkers({ you, ai }: { you: { out: number; next: number | null }; ai: { out: number; next: number | null } }) {
  if (you.out === 0 && ai.out === 0) return null
  const tip = [
    t('assoc.workersOn', 'You: {n} here, {next}', { n: you.out, next: nextUse(you.out, you.next) }),
    t('assoc.workersOnAi', 'AI: {n} here, {next}', { n: ai.out, next: nextUse(ai.out, ai.next) }),
  ].join('\n')
  return (
    <Tip tip={<span className="whitespace-pre-line">{tip}</span>} className="ml-auto flex cursor-help items-center -space-x-1">
      {Array.from({ length: you.out }, (_, i) => <WorkerIcon key={`y${i}`} className={`${YOU} text-white ring-2 ring-sky-100`} />)}
      {Array.from({ length: ai.out }, (_, i) => <WorkerIcon key={`a${i}`} className={`${AI} text-white ring-2 ring-sky-100`} />)}
    </Tip>
  )
}

/** A task's strength tag, as printed: white number on black. */
function StrengthTag({ n }: { n: number }) {
  return <span className="grid h-6 min-w-6 shrink-0 place-items-center rounded-sm bg-slate-900 px-1 text-[13px] font-black text-white">{n}</span>
}

/**
 * The association board, in the printed board's style: the donation column (pink), then the four tasks by
 * strength on the blue board. Partner zoos and universities show what is still there for you to take; the
 * ones you already have are greyed out (what each player has taken is on their zoo, beside the map).
 */
export function AssociationBoard({ board }: { board: Board }) {
  const tracks = board.tracks
  const a = tracks.association
  if (!a) return null
  const me = board.players.find((p) => p.you)!
  const you = tracks.players.find((p) => p.idx === me.idx)!
  const ai = tracks.players.find((p) => p.idx !== me.idx)!
  const yw = a.players.find((p) => p.idx === you.idx)!
  const aw = a.players.find((p) => p.idx === ai.idx)!
  const d = a.donations
  const cost = (task: TaskName) => (
    <TaskWorkers you={{ out: yw.out[task], next: yw.next[task] }} ai={{ out: aw.out[task], next: aw.next[task] }} />
  )
  const zooOpen = (id: string, available: boolean) => available && !me.partner_zoos.includes(id)
  const uniOpen = (id: string, available: boolean) => available && !me.universities.includes(id)
  const nextZoo = tracks.partner_zoos.slots.find((x) => x.slot === me.partner_zoos.length + 1)
  const zooLocked = !!nextZoo && nextZoo.slot >= tracks.partner_zoos.association_from && !you.association_ii

  return (
    <section className="overflow-hidden rounded-xl border bg-white shadow-xs" aria-label={t('assoc.title', 'Association board')}>
      <div className="flex items-center justify-between px-3 pt-2 pb-1.5">
        <Tip tip={t('assoc.titleTip', 'The tasks of the Association action. Side I: one task up to its strength. Side II: several different tasks with total strength up to it, then one donation. Each task takes association workers.')} className="cursor-help text-sm font-semibold">{t('assoc.title', 'Association board')}</Tip>
        <Tip tip={t('assoc.freeTip', 'Free association workers: you {you}, AI {ai}. They return at the break.', { you: yw.active, ai: aw.active })} className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-0.5">{Array.from({ length: yw.active }, (_, i) => <WorkerIcon key={i} className={`${YOU} text-white`} />)}</span>
          <span className="flex items-center gap-0.5">{Array.from({ length: aw.active }, (_, i) => <WorkerIcon key={i} className={`${AI} text-white`} />)}</span>
        </Tip>
      </div>
      <div className="space-y-px bg-sky-300/60 p-px">
        <div className="flex items-center gap-2 bg-sky-100 px-2 py-1.5">
          <StrengthTag n={2} />
          <Tip className="flex cursor-help items-center gap-1 text-xs font-semibold" tip={t('assoc.reputationTip', 'Gain 2 reputation. Higher reputation reaches more display folders and passes the bonus spaces on the reputation track. Until your Cards action is upgraded (side II), reputation stops at 9 and any more is lost. Above 15, each extra point becomes 1 appeal.')}><Reward kind="reputation" amount={2} /> {t('assoc.reputationShort', 'Reputation')}</Tip>
          {cost('reputation')}
        </div>
        <div className="bg-sky-100 px-2 py-1.5">
          <div className="flex items-center gap-2">
            <StrengthTag n={3} />
            <Tip className="cursor-help text-xs font-semibold" tip={<>
              <span>{t('assoc.partnerRule', 'Each gives its continent icon, and its animals cost {n} less.', { n: tracks.partner_zoos.discount })}</span>
              <span>{nextZoo
                ? t('assoc.nextZoo', 'Your space {n}: {bonus}', { n: nextZoo.slot, bonus: nextZoo.label }) + (zooLocked ? t('assoc.needsII', ' (needs Association II)') : '')
                : t('assoc.zoosFull', 'Your partner zoo spaces are full')}</span>
            </>}>{t('assoc.partnerZoo', 'Partner zoo')}</Tip>
            {cost('partner_zoo')}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {a.partner_zoos.map((z) => {
              const open = zooOpen(z.id, z.available)
              const name = ICON_META[z.id]?.label ?? z.id
              return (
                <Tip key={z.id} tip={open ? name : `${name}: ${t('assoc.haveIt', 'You already have it')}`}
                  className={cn('grid size-8 place-items-center rounded-full bg-white shadow-xs ring-1 ring-sky-200', !open && 'opacity-35 grayscale')}>
                  <GameIcon name={z.id} size={24} />
                </Tip>
              )
            })}
          </div>
        </div>
        <div className="bg-sky-100 px-2 py-1.5">
          <div className="flex items-center gap-2">
            <StrengthTag n={4} />
            <Tip className="cursor-help text-xs font-semibold" tip={t('assoc.universityTip', 'Take one university you do not have yet: science icons, reputation or a hand limit of 5. Filling your university spaces beside the map may also give a bonus.')}>{t('assoc.university', 'University')}</Tip>
            {cost('university')}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {a.universities.map((u) => {
              const open = uniOpen(u.id, u.available)
              return (
                <Tip key={u.id} tip={open ? u.grant : `${u.grant}: ${t('assoc.haveIt', 'You already have it')}`} className={cn('inline-flex', !open && 'opacity-35 grayscale')}>
                  <UniversityChip id={u.id} title="" />
                </Tip>
              )
            })}
          </div>
        </div>
        <div className="flex items-center gap-2 bg-sky-100 px-2 py-1.5">
          <StrengthTag n={5} />
          <Tip className="cursor-help text-xs font-semibold" tip={t('assoc.projectHint', 'takes a map token, gives its bonus')}>{t('assoc.projectShort', 'Support a project')}</Tip>
          {cost('project')}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t-2 border-dashed border-pink-300 bg-pink-200/70 px-2 py-1.5">
        <Tip tip={t('assoc.donationTip', 'Needs Association II. Once per action, after doing a task: pay the next price for +1 conservation.')} className="cursor-help text-xs font-semibold text-pink-950">
          {t('assoc.donation', 'Donation')}
        </Tip>
        <div className="flex flex-wrap items-center gap-1">
          {d.costs.map((c, i) => (
            <span key={i} className={cn('grid h-6 min-w-7 place-items-center rounded-md px-1 text-[11px] font-black tabular-nums',
              i < d.made ? 'bg-slate-400/40 text-slate-500 line-through' : i === d.made ? 'bg-slate-800 text-white ring-2 ring-pink-500' : 'bg-slate-700/80 text-white')}>{c}</span>
          ))}
          <span className={cn('grid h-6 place-items-center rounded-md px-1.5 text-[11px] font-black', d.made >= d.costs.length ? 'bg-slate-800 text-white ring-2 ring-pink-500' : 'bg-slate-700/80 text-white')}>∞ {d.final}</span>
        </div>
      </div>

    </section>
  )
}

/** One player's map tokens (the left edge of the printed zoo map), icons only: what each gives, whether it pays
 * again every break, and whether it is taken are on hover. */
export function MapTokens({ board, idx }: { board: Board; idx: number }) {
  const tracks = board.tracks
  const p = tracks.players.find((x) => x.idx === idx)
  if (!p || tracks.tokens.length === 0) return null
  const left = tracks.tokens.filter((tk) => p.on_map[tk.index] !== false).length
  return (
    <div className="rounded-lg bg-amber-50 p-1.5">
      <Tip side="top" tip={t('tokens.rule', 'Supporting a conservation project takes one and gives its bonus.')} className="mb-1 flex cursor-help items-center justify-between font-semibold text-amber-950">
        <span>{t('tracks.mapTokens', 'Map tokens')}</span>
        <span className="text-[10px] font-medium">{t('tokens.left', '{n} left', { n: left })}</span>
      </Tip>
      <div className="grid grid-cols-2 gap-1">
        {tracks.tokens.map((tk) => {
          const on = p.on_map[tk.index] !== false
          const tip = [
            tk.label,
            tk.repeats ? t('tokens.repeat', 'pays again every break') : t('tokens.once', 'once'),
            on ? null : tk.repeats ? t('tokens.active', '· taken, paying') : t('tokens.taken', '· taken'),
          ].filter(Boolean).join(' · ').replace(' · ·', ' ·')
          return (
            <Tip key={tk.index} side="left" tip={tip}
              className={cn('flex h-8 cursor-help items-center justify-center gap-0.5 rounded-md border', on ? 'border-amber-200 bg-white' : 'border-emerald-300 bg-emerald-50 opacity-60')}>
              {tk.repeats ? <RepeatMark /> : <OnceMark />}
              <span className="scale-90">{tk.effects.length ? <Rewards effects={tk.effects} /> : <CircleHelp className="size-4 text-slate-400" />}</span>
            </Tip>
          )
        })}
      </div>
    </div>
  )
}

/**
 * The side of a zoo map, as printed beside it: the partner zoo spaces (pink) and university spaces (blue) with
 * what this player has taken, the bonus each next space gives, and the association workers.
 */
export function ZooSide({ board, player }: { board: Board; player: Player }) {
  const tracks = board.tracks
  const tp = tracks.players.find((x) => x.idx === player.idx)
  if (!tp) return null
  const assoc = tracks.association
  const free = assoc?.players.find((x) => x.idx === player.idx)?.active ?? tp.workers
  const uni = (id: string) => assoc?.universities.find((u) => u.id === id)
  const slot = (filled: ReactNode | null, effects: TrackEffect[], n: number, locked: boolean, tone: string, label: string) => (
    <div key={n} className={cn('flex min-h-8 items-center gap-1 rounded-md border px-1 py-1', filled ? `bg-white ${tone}` : 'border-dashed border-slate-300 bg-white/50')}>
      <span className="w-3 text-[10px] font-bold text-slate-500">{n}</span>
      {filled ?? (
        <Tip side="left" tip={<>
          <span>{effects.length ? t('side.spaceGives', 'Space {n} bonus: {bonus}', { n, bonus: label }) : t('side.spaceNothing', 'Space {n}: no bonus', { n })}</span>
          {locked && <span className="text-red-700">{t('side.spaceLocked', 'Needs Association II (upgraded) to take this one.')}</span>}
        </>} className={cn('flex flex-1 cursor-help items-center gap-1 text-[10px] text-slate-500', locked && 'opacity-60')}>
          {effects.length ? <Rewards effects={effects} /> : <span>—</span>}
          {locked && <Lock className="size-3 text-red-600" />}
        </Tip>
      )}
    </div>
  )
  return (
    <div className="grid w-full grid-cols-[repeat(auto-fill,minmax(160px,1fr))] items-start gap-2 text-xs @xl:flex @xl:flex-col @xl:items-stretch">
      <MapTokens board={board} idx={player.idx} />
      <div className="grid grid-cols-2 gap-1.5">
      <div className="rounded-lg bg-pink-100/70 p-1">
        <Tip side="top" tip={t('assoc.partnerRule', 'Each gives its continent icon, and its animals cost {n} less.', { n: tracks.partner_zoos.discount })} className="mb-1 flex cursor-help items-center gap-0.5 text-[11px] font-semibold whitespace-nowrap text-pink-950">
          <Handshake className="size-3.5 shrink-0" />{t('tracks.partnerZoos', 'Partner zoos')}
        </Tip>
        <div className="flex flex-col gap-1">
          {[...tracks.partner_zoos.slots].reverse().map((s) => {
            const c = player.partner_zoos[s.slot - 1]
            return slot(c ? <Tip tip={ICON_META[c]?.label ?? c} className="flex flex-1 items-center"><GameIcon name={c} size={18} /></Tip> : null, s.effects, s.slot,
              s.slot >= tracks.partner_zoos.association_from && !tp.association_ii, 'border-pink-300', s.label)
          })}
        </div>
      </div>
      <div className="rounded-lg bg-sky-100/70 p-1">
        <Tip side="top" tip={t('side.universitiesTip', 'Universities taken with the Association action (strength 4): science icons, reputation or a hand limit of 5. Each space filled may give a bonus.')} className="mb-1 flex cursor-help items-center gap-0.5 text-[11px] font-semibold whitespace-nowrap text-sky-950"><GraduationCap className="size-3.5 shrink-0" />{t('tracks.universities', 'Universities')}</Tip>
        <div className="flex flex-col gap-1">
          {[...tracks.universities.slots].reverse().map((s) => {
            const id = player.universities[s.slot - 1]
            const u = id ? uni(id) : undefined
            return slot(id ? <Tip tip={u?.grant ?? id} className="flex flex-1 items-center"><UniversityChip id={id} title="" /></Tip> : null, s.effects, s.slot, false, 'border-sky-300', s.label)
          })}
        </div>
      </div>
      </div>
      <div className="rounded-lg bg-slate-100 p-1.5">
        <div className="mb-1 flex items-center justify-between font-semibold">
          <Tip side="top" tip={t('side.workersTip', 'Association workers do the tasks on the association board; they return at the break. Dark: free; outlined: out on a task; dashed: not hired yet.')} className="flex cursor-help items-center gap-1"><Users className="size-3.5" />{t('tracks.workers', 'Workers')}</Tip>
          <span className="text-[10px] font-medium text-slate-600">{t('side.free', '{n} free', { n: free })}</span>
        </div>
        <div className="flex items-center gap-1">
          {Array.from({ length: tracks.workers.max }, (_, i) => (
            <Tip key={i} side="top" className={cn('grid size-5 cursor-help place-items-center rounded-full',
              i < free ? 'bg-slate-700 text-white' : i < tp.workers ? 'border border-slate-400 bg-white text-slate-400' : 'border border-dashed border-slate-300 text-slate-300')}
              tip={i < free ? t('side.workerFreeTip', 'Worker {n}: free for an association task', { n: i + 1 }) : i < tp.workers ? t('side.workerOutTip', 'Worker {n}: out on a task until the break', { n: i + 1 }) : t('side.workerNotYetTip', 'Worker {n}: not hired yet (track bonuses, map tokens and some cards hire more)', { n: i + 1 })}>
              <Users className="size-3" />
            </Tip>
          ))}
          {tracks.workers.last.length > 0 && tp.workers < tracks.workers.max && (
            <Tip side="top" tip={t('side.lastWorkerTip', 'Hiring your {n}th worker also gives {bonus}', { n: tracks.workers.max, bonus: tracks.workers.last.map((e) => e.label).join(', ') })} className="ml-1 flex cursor-help items-center gap-0.5 text-[10px] text-slate-500">{tracks.workers.max}: <Rewards effects={tracks.workers.last} /></Tip>
          )}
        </div>
      </div>
    </div>
  )
}
