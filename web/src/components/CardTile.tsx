import { Check, Globe, Hourglass, PawPrint, Repeat, Shield, Star, Award, Zap } from 'lucide-react'
import type { Card, CardStatus, Enclosure, ProjectSlot, SizeLimit } from '@/api/types'
import { t, term } from '@/i18n'
import { ACTIONS, CARD_TYPE_STYLE, iconMeta } from '@/lib/game'
import { cn } from '@/lib/utils'
import { GameIcon } from './GameIcon'
import { HoverPreview } from './HoverPreview'
import { RichText, TokenChip } from './Rich'

export type CardVariant = 'full' | 'compact' | 'detail'


const HEX = 'polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%)'

/** A conservation project's kind (base, normal, breed, release) in the board's language. */
export function projectCategory(category: string | undefined): string {
  if (!category) return ''
  return t(`projects.category${category[0].toUpperCase()}${category.slice(1)}`, category)
}

function Hex({ children, size = 30 }: { children: React.ReactNode; size?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center font-extrabold text-white"
      style={{ clipPath: HEX, width: size, height: size * 1.1, background: '#8a6a3d', fontSize: size * 0.5 }}
      title={t('cards.standardEnclosureSize', 'Standard enclosure size')}
    >
      {children}
    </span>
  )
}

export function EnclosureBadge({ enc }: { enc: Enclosure }) {
  return (
    <div className="flex items-center gap-1">
      {enc.size !== null && <Hex size={26}>{enc.size}</Hex>}
      {(enc.rock > 0 || enc.water > 0) && (
        <span className="flex flex-col gap-px">
          {enc.rock > 0 && (
            <span className="flex items-center gap-px text-[9px] leading-none font-bold" title={t('cards.rockAdjacent', '{count} rock', { count: enc.rock })}>
              <GameIcon name="rock" size={12} />×{enc.rock}
            </span>
          )}
          {enc.water > 0 && (
            <span className="flex items-center gap-px text-[9px] leading-none font-bold" title={t('cards.waterAdjacent', '{count} water', { count: enc.water })}>
              <GameIcon name="water" size={12} />×{enc.water}
            </span>
          )}
        </span>
      )}
    </div>
  )
}

function CostSquare({ base, effective }: { base?: number; effective?: number }) {
  const shown = effective ?? base
  if (shown === undefined) return null
  const differs = base !== undefined && effective !== undefined && effective !== base
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5" title={differs ? t('cards.costsForYou', 'Costs {effective} for you (printed {base})', { effective: effective ?? '', base: base ?? '' }) : t('cards.cost', 'Cost')}>
      <span className="inline-flex h-[22px] min-w-[22px] items-center justify-center gap-px rounded-md px-1 text-[12px] leading-none font-extrabold text-white" style={{ background: '#5f6368' }}>
        <span className="text-[8px] font-bold text-white/75">$</span>
        {shown}
      </span>
      {differs && <s className="text-[9px] text-slate-500">{base}</s>}
    </span>
  )
}

function ReqChip({ children, title, bold }: { children: React.ReactNode; title?: string; bold?: boolean }) {
  return (
    <span className={cn('inline-flex shrink-0 items-center gap-0.5 rounded-sm border px-1 text-[9px] leading-[1.35] whitespace-nowrap text-[#b42318]', bold ? 'border-[#b42318] bg-[#f8c9c6] font-extrabold' : 'border-[#f0a9a4] bg-[#fde2e1] font-semibold')} title={title}>
      {children}
    </span>
  )
}

const STRIP_BG: Record<string, string> = { animal: '#f3efe7', sponsor: '#dde7f2', project: '#dcebd6', endgame: '#efdcd3' }

function hasRequirements(card: Card) {
  return card.requirements.length > 0 || card.min_reputation !== undefined
}

/** One-line "Needs" strip under the name banner. */
function RequirementStrip({ card, status }: { card: Card; status: CardStatus | null | undefined }) {
  if (!hasRequirements(card)) return null
  const unmet = new Set(status && !status.ready ? (status.unmet ?? []) : [])
  const counts = new Map<string, number>()
  for (const r of card.requirements) counts.set(r, (counts.get(r) ?? 0) + 1)
  const chips: React.ReactNode[] = []
  for (const [r, n] of counts) {
    const m = iconMeta(r)
    if (m && r !== 'reputation' && r !== 'appeal') {
      chips.push(
        <ReqChip key={r} title={t('cards.needsIcons', 'Needs {count} {icon} icons', { count: n, icon: m.label })} bold={unmet.has(r)}>
          <GameIcon name={m.key} size={13} />×{n}
        </ReqChip>,
      )
    } else {
      const text =
        r === 'Partner Zoo' ? t('cards.partnerZoo', 'Partner Zoo')
        : r.endsWith('II') ? t('cards.upgradeII', '{action} II', { action: ACTIONS[r.slice(0, -2) as keyof typeof ACTIONS]?.label ?? r.slice(0, -2) })
        : r === 'reputation' ? t('cards.repAtLeast', 'rep ≥{value}', { value: card.min_reputation ?? '' })
        : r === 'appeal' ? t('cards.appealAtMost', 'appeal ≤{value}', { value: card.max_appeal ?? '' })
        : r
      chips.push(
        <ReqChip key={r} bold={unmet.has(r)}>
          {text}
        </ReqChip>,
      )
    }
  }
  if (!counts.has('reputation') && card.min_reputation !== undefined) chips.push(<ReqChip key="mr" bold={unmet.has('reputation')}>{t('cards.repAtLeast', 'rep ≥{value}', { value: card.min_reputation })}</ReqChip>)
  return (
    <div className="flex h-[18px] shrink-0 items-center gap-1 overflow-hidden border-l-[3px] border-orange-600 px-1" style={{ background: STRIP_BG[card.type] }}>
      <span className="text-[8px] font-bold tracking-wide text-[#b42318] uppercase">{t('cards.needs', 'Needs')}</span>
      {chips}
    </div>
  )
}

function sizeText(s: SizeLimit | number | null | undefined): string | null {
  if (s === null || s === undefined) return null
  if (typeof s === 'number') return t('cards.size', 'Size {size}', { size: s })
  if (s.min !== undefined && s.max !== undefined) return s.min === s.max ? t('cards.size', 'Size {size}', { size: s.min }) : t('cards.sizeRange', 'Size {min}-{max}', { min: s.min, max: s.max })
  if (s.min !== undefined) return t('cards.sizeMinimum', 'Size {min}+', { min: s.min })
  if (s.max !== undefined) return t('cards.sizeMaximum', 'Size ≤{max}', { max: s.max })
  return null
}

export function Rewards({ slot }: { slot: ProjectSlot }) {
  return (
    <>
      {slot.rewards.map((r, i) => (
        <TokenChip key={i} name={r.reward === 'conservation' ? 'ConservationPoint' : r.reward === 'reputation' ? 'Reputation' : r.reward} value={`+${r.amount}`} />
      ))}
    </>
  )
}

export function ProjectSlots({
  card,
  marker,
  className,
  layout = 'stacked',
}: {
  card: Card
  marker?: (position: number) => React.ReactNode
  className?: string
  layout?: 'stacked' | 'row'
}) {
  return (
    <ul
      className={cn(
        layout === 'row'
          ? 'grid grid-cols-3 divide-x divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-slate-50/60'
          : 'space-y-0.5',
        className,
      )}
    >
      {(card.slots ?? []).map((s) => {
        const sz = sizeText(s.size)
        return (
          <li
            key={s.position}
            className={cn(
              'flex items-center gap-1 text-[9.5px] leading-tight',
              layout === 'row' && 'min-w-0 flex-col justify-center gap-1 px-1 py-1.5',
            )}
          >
            <span className="flex min-w-0 flex-wrap items-center justify-center gap-1">
              {marker?.(s.position)}
              {s.required !== null && (
                <span className="inline-flex items-center gap-0.5 font-bold">
                  ≥{s.required}
                  {card.icon && iconMeta(card.icon) && <GameIcon name={card.icon} size={13} />}
                </span>
              )}
              {sz && <span className="rounded bg-green-200 px-1 font-semibold text-green-900">{sz}</span>}
            </span>
            <span className="flex flex-wrap items-center justify-center gap-1 text-muted-foreground">
              <span>→</span>
              <span className="flex items-center">
                <Rewards slot={s} />
              </span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function EffectMark({ timing }: { timing: string }) {
  switch (timing) {
    case 'passive':
      return <span className="mt-[2px] size-2.5 shrink-0 rounded-full bg-blue-500 ring-1 ring-blue-800" title={t('cards.eachTime', 'Each time')} />
    case 'income':
      return (
        <span className="mt-px grid size-3.5 shrink-0 place-items-center rounded-[3px] border border-purple-800 bg-purple-600 text-white" title={t('cards.incomeAgain', 'Income: again at every break')}>
          <Repeat className="size-2.5" strokeWidth={3} />
        </span>
      )
    case 'immediate':
      return (
        <span className="mt-px grid size-3.5 shrink-0 place-items-center rounded-[3px] border border-yellow-600 bg-yellow-300 text-yellow-950" title={t('cards.immediate', 'Immediate')}>
          <Zap className="size-2.5" strokeWidth={3} />
        </span>
      )
    case 'endgame':
      return (
        <span className="mt-px grid size-3.5 shrink-0 place-items-center rounded-[3px] bg-amber-800 text-white" title={t('cards.endOfGame', 'End of game')}>
          <Hourglass className="size-2.5" />
        </span>
      )
    default:
      return null
  }
}

function Gains({ card }: { card: Card }) {
  return (
    <div className="flex shrink-0 items-center gap-1">
      {card.appeal !== 0 && (
        <span className="inline-flex items-center gap-px rounded-sm bg-orange-500 px-1 text-[11px] leading-[1.3] font-extrabold text-white" title={t('playerPanel.appeal', 'Appeal')}>
          <Star className="size-2.5 fill-white" />
          {card.appeal > 0 ? `+${card.appeal}` : card.appeal}
        </span>
      )}
      {card.conservation !== 0 && (
        <span className="inline-flex items-center gap-px rounded-full bg-emerald-600 px-1 text-[11px] leading-[1.3] font-bold text-white" title={t('playerPanel.conservation', 'Conservation points')}>
          <Shield className="size-2.5" strokeWidth={2.8} />
          {card.conservation}
        </span>
      )}
      {card.reputation !== 0 && (
        <span className="inline-flex items-center gap-px rounded-full px-1 text-[11px] leading-[1.3] font-bold text-white" style={{ background: '#4a78c8' }} title={t('playerPanel.reputation', 'Reputation')}>
          <Award className="size-2.5" strokeWidth={2.8} />
          {card.reputation}
        </span>
      )}
    </div>
  )
}

function Footer({ card, status, detail }: { card: Card; status: CardStatus | null | undefined; detail: boolean }) {
  return (
    <div className={cn('flex shrink-0 items-center justify-between gap-1 border-t border-black/10 px-1.5', 'min-h-6 py-0.5')}>
      <div className="min-w-0 flex-1">
        {status &&
          (status.ready ? (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-600 px-1.5 py-px text-[9px] leading-tight font-bold text-white">
              <Check className="size-2.5" strokeWidth={3.5} /> {t('cards.playable', 'Playable')}
            </span>
          ) : (
            <span className={cn('block leading-tight font-medium text-[#b42318]', detail ? 'text-xs' : 'line-clamp-2 text-[11px]')} title={status.why}>
              {status.why}
            </span>
          ))}
      </div>
      <Gains card={card} />
    </div>
  )
}

function Header({ card, status, compact }: { card: Card; status: CardStatus | null | undefined; compact?: boolean }) {
  const ts = CARD_TYPE_STYLE[card.type] ?? CARD_TYPE_STYLE.animal
  const tags = card.tags
  const stack = tags.length > 3
  let left: React.ReactNode = null
  if (card.type === 'animal') {
    const enc = card.enclosure
    left = (
      <div className="flex min-w-0 flex-col gap-0.5">
        <div className="flex items-center gap-1.5">
          {enc && enc.size !== null && (
            <span className="grid shrink-0 place-items-center text-[16px] font-extrabold text-white" style={{ clipPath: HEX, width: 34, height: 37, background: '#8a6a3d' }} title={t('cards.standardEnclosureSize', 'Standard enclosure size')}>
              {enc.size}
            </span>
          )}
          <CostSquare base={card.cost} effective={status?.cost} />
        </div>
        {enc && (enc.rock > 0 || enc.water > 0 || enc.special.length > 0) && (
          <div className={cn('flex items-center gap-1 text-[9px] leading-none font-bold', compact && 'flex-wrap')}>
            {enc.rock > 0 && <span className="flex items-center gap-px"><GameIcon name="rock" size={11} />×{enc.rock}</span>}
            {enc.water > 0 && <span className="flex items-center gap-px"><GameIcon name="water" size={11} />×{enc.water}</span>}
            {enc.special.map((s, i) => (
              <span key={i} className={cn('rounded border border-violet-400 bg-violet-100 px-1 text-[8px] leading-[1.2] font-semibold text-violet-900', !compact && 'truncate')}>
                {enc.size !== null && i === 0 ? `${t('cards.or', 'or')} ` : ''}
                {term('specialEnclosures', s.type, s.type)}
                {s.size > 0 ? ` ${s.size}` : ''}
              </span>
            ))}
          </div>
        )}
      </div>
    )
  } else if (card.type === 'sponsor') {
    left = (
      <div className="flex items-center gap-1.5">
        <span className="grid size-9 place-items-center rounded-lg bg-black text-[20px] leading-none font-extrabold text-white" title={t('cards.sponsorLevel', 'Sponsor level {level}', { level: card.level ?? '' })}>
          {card.level}
        </span>
        {status && status.cost > 0 && <CostSquare effective={status.cost} />}
      </div>
    )
  } else {
    const m = card.icon ? iconMeta(card.icon) : undefined
    left = (
      <span className="grid size-11 shrink-0 place-items-center rounded-lg text-white" style={{ background: ts.banner }}>
        {card.type === 'endgame' ? <Hourglass className="size-6" /> : m ? <GameIcon name={m.key} size={32} /> : card.icon?.startsWith('animal') ? <PawPrint className="size-6" /> : <Globe className="size-6" />}
      </span>
    )
  }
  return (
    <div className={cn('flex shrink-0 items-start justify-between gap-1 px-1.5 py-1', compact ? 'min-h-[52px]' : 'min-h-[54px]')}>
      {left}
      {card.type === 'project' ? (
        <span className="text-[10px] font-bold tracking-wide text-green-900 uppercase">{projectCategory(card.category)}</span>
      ) : (
        <div className="flex shrink-0 items-center pt-0.5">
          {tags.map((tg, i) => (
            <span key={i} className="rounded-full ring-2 ring-white" style={{ marginLeft: i === 0 ? 0 : stack ? -7 : 2 }}>
              <GameIcon name={tg} size={stack ? 20 : 22} />
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Sponsor effects as lines, one marker per timing. An icon-only effect repeats another one's text on
 * the printed card (Science Lab: the income also happens once when played), so it shares that line.
 * A leading "Income:" is dropped because the marker says it.
 */
function sponsorLines(card: Card): { timings: string[]; text: string }[] {
  const clean = (text: string) => text.replace(/^\s*(\*\*)?(Income:|收入[：:])(\*\*)?\s*/i, '')
  const lines = card.effects.filter((e) => !e.icon_only).map((e) => ({ timings: [e.timing], text: clean(e.text) }))
  for (const e of card.effects.filter((x) => x.icon_only)) {
    const same = lines.find((l) => l.text === clean(e.text))
    if (same) same.timings.unshift(e.timing)
    else lines.push({ timings: [e.timing], text: clean(e.text) })
  }
  return lines
}

function Body({ card, detail }: { card: Card; detail: boolean }) {
  return (
    <div className="space-y-1">
      {(card.type === 'project' || card.type === 'endgame' || card.type === 'animal') && card.text.map((t, i) => <RichText key={i} text={t} className="block" />)}
      {card.type === 'endgame' && card.scoring && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {card.scoring.map((s) => (
            <span key={s.threshold} className="flex flex-col items-center rounded border border-amber-800/30 bg-white/70 px-1 leading-tight" title={t('cards.thresholdScores', '{threshold}+ scores {conservation} conservation', { threshold: s.threshold, conservation: s.conservation })}>
              <span className="text-[9px] font-bold text-amber-950">≥{s.threshold}</span>
              <span className="inline-flex items-center gap-px text-[9px] font-bold text-emerald-700">
                +{s.conservation}
                <Shield className="size-2.5" />
              </span>
            </span>
          ))}
        </div>
      )}
      {card.type === 'project' && <ProjectSlots card={card} className="pt-0.5" />}
      {card.type === 'animal' &&
        card.abilities.map((a, i) => (
          <p key={i}>
            <b className="mr-1 rounded bg-slate-200 px-1 text-[9px] text-[#1f2937]">{a.name}</b> <RichText text={a.text} />
          </p>
        ))}
      {card.type === 'sponsor' &&
        sponsorLines(card).map((line, i) => (
          <p key={i} className="flex items-start gap-1">
            {line.timings.map((t) => (
              <EffectMark key={t} timing={t} />
            ))}
            <RichText text={line.text} className="min-w-0 flex-1" />
          </p>
        ))}
      {card.type === 'sponsor' && card.text.map((t, i) => <RichText key={i} text={t} className="block" />)}
      {detail && card.type === 'animal' && card.latin && <p className="text-[8.5px] text-slate-500 italic">{card.latin}</p>}
    </div>
  )
}

interface PrintedProps {
  card: Card
  variant?: CardVariant
  status?: CardStatus | null
  selected?: boolean
  dim?: boolean
  className?: string
}

/** A card laid out like the printed one, as fixed regions: header, name banner, body, footer. */
export function PrintedCard({ card, variant = 'full', status: statusProp, selected, dim, className }: PrintedProps) {
  const ts = CARD_TYPE_STYLE[card.type] ?? CARD_TYPE_STYLE.animal
  const status = statusProp !== undefined ? statusProp : card.status
  const detail = variant === 'detail'
  const compact = variant === 'compact'
  return (
    <div className={cn('relative', compact ? 'w-full' : 'w-[168px] shrink-0', className)}>
      <div
        className={cn(
          'flex flex-col overflow-hidden rounded-lg border border-slate-500/50 text-left shadow-xs transition',
          compact ? '' : detail ? 'min-h-[236px]' : 'h-[236px]',
          dim && 'opacity-70 grayscale-[0.5]',
          selected && 'ring-[3px] ring-sky-500 ring-offset-1',
        )}
        style={{ background: ts.bg }}
      >
        <Header card={card} status={status} compact={compact} />
        <div
          className={cn(
            'shrink-0 px-1.5 py-[3px] leading-[1.25] font-bold text-white',
            compact ? 'text-[12px] break-words' : !detail && 'truncate',
            !compact && (card.name.length > 22 ? 'text-[11px]' : 'text-[12.5px]'),
          )}
          style={{ background: ts.banner }}
          title={card.name}
        >
          {card.name}
        </div>
        {!compact && <RequirementStrip card={card} status={status} />}
        <div className={cn('relative min-h-0 px-1.5 py-1 text-[9.5px] leading-[1.25]', compact ? 'max-h-[3.4em] overflow-hidden' : detail ? 'flex-1' : 'flex-1 overflow-hidden')}>
          <Body card={card} detail={detail} />
          {!detail && !compact && <div className="pointer-events-none absolute inset-x-0 bottom-0 h-3" style={{ background: `linear-gradient(transparent, ${ts.bg})` }} />}
        </div>
        <Footer card={card} status={status} detail={detail} />
      </div>
      {selected && (
        <span className="absolute -top-2 -right-2 z-10 grid size-6 place-items-center rounded-full bg-sky-500 text-white shadow-md ring-2 ring-white">
          <Check className="size-4" strokeWidth={3.5} />
        </span>
      )}
    </div>
  )
}

interface CardTileProps {
  card: Card
  /** Overrides card.status (the display carries its own). */
  status?: CardStatus | null
  variant?: 'full' | 'compact'
  selected?: boolean
  disabled?: boolean
  dim?: boolean
  onClick?: () => void
  className?: string
}

export function CardPreview({ card, status }: { card: Card; status?: CardStatus | null }) {
  return (
    <div style={{ zoom: 1.78 }}>
      <PrintedCard card={card} variant="detail" status={status} />
    </div>
  )
}

export function CardTile({ card, status, variant = 'full', selected, disabled, dim, onClick, className }: CardTileProps) {
  const clickable = !!onClick && !disabled
  return (
    <HoverPreview
      preview={<CardPreview card={card} status={status} />}
      className={cn('transition', variant === 'full' ? 'shrink-0' : 'w-full', clickable && 'cursor-pointer hover:-translate-y-0.5', selected && '-translate-y-2', disabled && 'opacity-45', className)}
      triggerProps={{
        role: onClick ? 'button' : undefined,
        tabIndex: clickable ? 0 : undefined,
        'aria-pressed': onClick ? !!selected : undefined,
        'aria-disabled': disabled || undefined,
        onClick: clickable ? onClick : undefined,
        onKeyDown: (e) => {
          if (clickable && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            onClick()
          }
        },
      }}
    >
      <PrintedCard card={card} variant={variant} status={status} selected={selected} dim={dim} />
    </HoverPreview>
  )
}

/** One-line card reference with a hover preview; falls back to the raw id when the card is unknown. */
export function CardChip({ id, card }: { id: string; card: Card | undefined }) {
  if (!card) return <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{t('cards.unknownCard', 'Unknown card #{id}', { id })}</span>
  const ts = CARD_TYPE_STYLE[card.type]
  return (
    <HoverPreview as="span" preview={<CardPreview card={card} />} className="inline-flex cursor-help items-center gap-1 rounded border bg-white px-1.5 py-0.5 text-xs">
      <span className="size-1.5 rounded-full" style={{ background: ts?.banner }} />
      {card.name}
    </HoverPreview>
  )
}
