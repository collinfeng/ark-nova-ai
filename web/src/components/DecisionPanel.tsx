import { useEffect, useState } from 'react'
import { ArrowLeft, Check, Minus, Plus, Sparkles } from 'lucide-react'
import type { Board, Card, Option, Player } from '@/api/types'
import { t } from '@/i18n'
import { ACTIONS, buildingStyle, pct, type PlaceGroup } from '@/lib/game'
import { buildingEffect } from '@/lib/buildings'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ActionTile } from './ActionTile'
import { CardChip, CardTile } from './CardTile'
import { OptionIcon } from './OptionIcon'
import { Amount, XTokenMark } from './Resource'

interface Props {
  board: Board
  me: Player
  cardsById: Map<string, Card>
  hints: boolean
  busy: boolean
  /** Currently chosen building group while placing (null = still choosing). */
  group: PlaceGroup | null
  groups: PlaceGroup[]
  onGroup: (id: string | null) => void
  onMove: (index: number) => void
  /** Several options of this decision in a row, given by their keys */
  onMoveMany: (keys: string[][]) => void
  onHoverOption: (o: Option | null) => void
  /** Bumped by Undo to drop picks not yet confirmed (ticked cards, X-tokens): the pickers start afresh. */
  reset: number
  /** Whether a picker holds picks not yet confirmed, so Undo clears those before undoing a move. */
  onDraft: (has: boolean) => void
}

/** Tells the page whether this picker holds unconfirmed picks (and that it holds none once it is gone). */
function useDraft(has: boolean, onDraft: (has: boolean) => void) {
  useEffect(() => onDraft(has), [has, onDraft])
  useEffect(() => () => onDraft(false), [onDraft])
}

function ProbBar({ p, best }: { p: number | undefined; best: boolean }) {
  return (
    <span className="flex w-28 shrink-0 items-center gap-1.5">
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <span className={cn('block h-full rounded-full', best ? 'bg-sky-500' : 'bg-slate-400')} style={{ width: `${Math.min(100, (p ?? 0) * 100)}%` }} />
      </span>
      <span className="w-9 text-right text-[11px] text-muted-foreground tabular-nums">{pct(p)}</span>
    </span>
  )
}

function SetupKeep({ board, cardsById, busy, onMove, hints, onDraft }: Pick<Props, 'board' | 'cardsById' | 'busy' | 'onMove' | 'hints' | 'onDraft'>) {
  const d = board.decision!
  const [picked, setPicked] = useState<string[]>([])
  useDraft(picked.length > 0, onDraft)
  const need = d.keep_count ?? 4
  const match = d.options.find((o) => o.cards.length === picked.length && o.cards.every((c) => picked.includes(c)))
  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < need ? [...p, id] : p))
  const aiBest = d.ai ? d.options.find((o) => o.index === d.ai!.best) : undefined
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 px-1 pt-3 pb-1">
        {(d.keep_from ?? []).map((id) => {
          const card = cardsById.get(id)
          return card ? (
            <CardTile key={id} card={card} selected={picked.includes(id)} onClick={() => toggle(id)} disabled={busy} />
          ) : (
            <span key={id}>#{id}</span>
          )
        })}
      </div>
      <div className="flex items-center gap-3">
        <span className={cn('rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums', picked.length === need ? 'bg-sky-500 text-white' : 'bg-muted text-foreground')}>
          {t('decision.confirmKeep', 'Keep {count}/{need}', { count: picked.length, need })}
        </span>
        <Button disabled={busy || !match} onClick={() => match && onMove(match.index)}>
          <Check /> {t('decision.confirm', 'Confirm')}
        </Button>
        {hints && match && <span className="text-xs text-muted-foreground">{t('decision.aiGivesKeep', 'AI gives this keep {chance}', { chance: pct(match.ai_prob) })}</span>}
        {hints && aiBest && (
          <Button variant="ghost" size="sm" onClick={() => setPicked(aiBest.cards)}>
            <Sparkles /> {t('decision.useAiPick', "Use the AI's pick")}
          </Button>
        )}
      </div>
    </div>
  )
}

function TurnTiles({ board, me, hints, busy, onMove, onDraft }: Pick<Props, 'board' | 'me' | 'hints' | 'busy' | 'onMove' | 'onDraft'>) {
  const d = board.decision!
  const [x, setX] = useState(0)
  const [spend, setSpend] = useState(false)
  useDraft(x !== 0 || spend, onDraft)
  const acts = d.options.filter((o) => o.type === 'act')
  const xtokens = d.options.filter((o) => o.type === 'xtoken')
  const xs = [...new Set(acts.map((o) => o.x ?? 0))].sort((a, b) => a - b)
  // Only an action or an X-token is described here; any other favourite (none today) gets no line.
  const best = d.ai ? d.options.find((o) => o.index === d.ai!.best && (o.type === 'act' || o.type === 'xtoken') && !!o.action && o.action in ACTIONS) : undefined
  const bestText = best
    ? best.type === 'xtoken'
      ? t('decision.takeXWith', 'Take X-token with {action}', { action: ACTIONS[best.action!].label })
      : (best.x ?? 0) > 0
        ? t('decision.actionWithX', '{action} with +{x} X', { action: ACTIONS[best.action!].label, x: best.x })
        : ACTIONS[best.action!].label
    : ''
  // The AI's odds for how many X-tokens to spend (all actions together) and for taking one instead
  const xOdds = (v: number) => acts.filter((o) => (o.x ?? 0) === v).reduce((sum, o) => sum + (o.ai_prob ?? 0), 0)
  const takeOdds = xtokens.reduce((sum, o) => sum + (o.ai_prob ?? 0), 0)
  const bestX = best?.type === 'act' ? (best.x ?? 0) : null
  const bestHere = best && (spend ? best.type === 'xtoken' : best.type === 'act' && (best.x ?? 0) === x)
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {!spend && xs.length > 1 && me.xtokens > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 font-medium"><XTokenMark className="size-3.5" />{t('decision.useXTokens', 'Use X-tokens')}</span>
            <div className="inline-flex rounded-lg bg-muted p-0.5">
              {xs.map((v) => (
                <button
                  key={v}
                  type="button"
                  disabled={busy}
                  onClick={() => setX(v)}
                  className={cn('rounded-md px-2.5 py-0.5 font-medium tabular-nums', x === v ? 'bg-violet-600 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground')}
                >
                  {v === 0 ? '0' : `+${v}`}
                  {hints && d.ai && (
                    <span className={cn('ml-1 text-[10px] font-normal', x === v ? 'text-white/80' : bestX === v ? 'font-semibold text-sky-700' : 'text-muted-foreground/70')} title={t('decision.xOddsTip', 'How likely the AI is to spend this many X-tokens')}>
                      {pct(xOdds(v))}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
        {xtokens.length > 0 && (
          <Button
            variant={spend ? 'default' : 'outline'}
            size="sm"
            disabled={busy}
            onClick={() => {
              setSpend((v) => !v)
              setX(0)
            }}
          >
            <XTokenMark className="size-3.5" />
            {t('decision.takeXInstead', 'Take X-token instead')}
            {hints && d.ai && <span className={cn('ml-1 text-[10px] font-normal', best?.type === 'xtoken' ? 'font-semibold text-sky-700' : 'text-muted-foreground')}>{pct(takeOdds)}</span>}
          </Button>
        )}
        {spend && <span className="text-muted-foreground">{t('decision.takeXExplanation', 'The action card you click goes back to slot 1 and you gain an X-token.')}</span>}
        {hints && best && !bestHere && (
          <span className="flex items-center gap-1 text-sky-800">
            <Sparkles className="size-3" /> {t('decision.aiPrefers', 'AI prefers: {choice}', { choice: bestText })}
          </span>
        )}
      </div>
      <div className="grid grid-cols-5 gap-2">
        {me.slots.map((slot, i) => {
          const option = spend
            ? xtokens.find((o) => o.action === slot.action)
            : acts.find((o) => o.action === slot.action && (o.x ?? 0) === x)
          const anyAct = acts.some((o) => o.action === slot.action)
          const reason = spend
            ? t('decision.cannotTakeX', 'Cannot take an X-token with this card')
            : x > 0 && anyAct
              ? t('decision.notPossibleWithX', 'Not possible with +{count}', { count: x })
              : (slot.reason ?? t('decision.noLegalMove', 'No legal move with this action right now'))
          return (
            <ActionTile
              key={`${slot.action}-${i}`}
              slot={slot}
              slots={me.slots}
              option={option}
              mode={spend ? 'xtoken' : 'act'}
              x={x}
              reason={reason}
              hints={hints}
              isBest={!!option && option.index === d.ai?.best}
              busy={busy}
              onPlay={onMove}
            />
          )
        })}
      </div>
    </div>
  )
}

/** Take or discard several cards in one go: tick the cards (the deck as many times as wanted), then
 *  confirm once. The moves are played back to back. */
function MultiPick({
  decision,
  options,
  cardsById,
  hints,
  busy,
  onConfirm,
  onHoverOption,
  onDraft,
}: {
  decision: NonNullable<Board['decision']>
  options: Option[]
  cardsById: Map<string, Card>
  hints: boolean
  busy: boolean
  onConfirm: (keys: string[][]) => void
  onHoverOption: (o: Option | null) => void
  onDraft: (has: boolean) => void
}) {
  const discarding = decision.kind === 'discard_hand'
  const [counts, setCounts] = useState<Record<number, number>>({})
  useDraft(Object.values(counts).some((n) => n > 0), onDraft)
  const repeats = (o: Option) => o.key[0] === 'deck'
  const available = options.reduce((s, o) => s + (repeats(o) ? decision.pick!.count : 1), 0)
  const total = Math.min(decision.pick!.count, available)
  // A rule policy decides one card at a time (it looks again after each), so with its hint on you pick one,
  // confirm, and get its next suggestion for the rest.
  const rule = hints && !!decision.ai?.rule
  const need = rule ? 1 : total
  const chosen = Object.values(counts).reduce((s, n) => s + n, 0)
  const recommended: { option: Option; count: number }[] = []
  if (hints) {
    let left = need
    for (const option of [...options].sort((a, b) => (b.ai_prob ?? 0) - (a.ai_prob ?? 0))) {
      const count = Math.min(left, repeats(option) ? need : 1)
      if (count > 0) recommended.push({ option, count })
      left -= count
      if (left === 0) break
    }
  }
  const recommendedIndexes = new Set(recommended.map(({ option }) => option.index))
  const useRecommended = () => {
    const next: Record<number, number> = {}
    for (const { option, count } of recommended) next[option.index] = count
    setCounts(next)
  }
  const set = (o: Option, n: number) =>
    setCounts((c) => {
      const others = chosen - (c[o.index] ?? 0)
      const next = Math.max(0, Math.min(repeats(o) ? need : 1, n, need - others))
      return { ...c, [o.index]: next }
    })
  const confirm = () => {
    const keys: string[][] = []
    for (const o of options) for (let i = 0; i < (counts[o.index] ?? 0); i++) keys.push(o.key as string[])
    onConfirm(keys)
  }
  return (
    <div className="flex flex-col gap-1.5">
      {hints && recommended.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950">
          <Sparkles className="size-3.5 shrink-0 text-sky-600" />
          <span className="font-semibold">{rule ? t('decision.rulePick', "Rule policy's pick:") : t('decision.aiRecommended', 'AI preference:')}</span>
          <span className="min-w-0 flex-1">
            {recommended
              .map(({ option, count }) => (count > 1 ? `${option.label} ×${count}` : option.label))
              .join(t('common.listSep', ', '))}
          </span>
          <Button variant="outline" size="sm" disabled={busy} onClick={useRecommended}>
            {rule ? t('decision.useRulePick', "Use the rule's pick") : t('decision.useAiPick', "Use the AI's pick")}
          </Button>
        </div>
      )}
      {options.map((o) => {
        const n = counts[o.index] ?? 0
        const aiChoice = hints && recommendedIndexes.has(o.index)
        return (
          <div
            key={o.index}
            role={repeats(o) ? undefined : 'checkbox'}
            aria-checked={repeats(o) ? undefined : n > 0}
            tabIndex={busy ? -1 : 0}
            onMouseEnter={() => onHoverOption(o)}
            onMouseLeave={() => onHoverOption(null)}
            onClick={() => !busy && !repeats(o) && set(o, n ? 0 : 1)}
            onKeyDown={(e) => {
              if (!busy && !repeats(o) && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault()
                set(o, n ? 0 : 1)
              }
            }}
            className={cn(
              'flex items-center gap-3 rounded-lg border bg-white px-3 py-2 text-sm transition',
              !repeats(o) && 'cursor-pointer hover:border-sky-400 hover:bg-sky-50/50',
              aiChoice && n === 0 && 'border-sky-300 bg-sky-50/30',
              n > 0 && (discarding ? 'border-rose-400 bg-rose-50/60 ring-1 ring-rose-400' : 'border-sky-500 bg-sky-50/60 ring-1 ring-sky-500'),
              busy && 'cursor-wait opacity-60',
            )}
          >
            <OptionIcon option={o} cardsById={cardsById} />
            <span className="flex-1">{o.label}</span>
            {o.cards.length > 0 && (
              <span className="flex flex-wrap justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                {o.cards.map((id) => (
                  <CardChip key={id} id={id} card={cardsById.get(id)} />
                ))}
              </span>
            )}
            {aiChoice && <Sparkles className="size-3.5 shrink-0 text-sky-600" aria-label={t('accessibility.aiFavorite', "AI's favourite")} />}
            {hints && <ProbBar p={o.ai_prob} best={o.index === decision.ai?.best} />}
            {repeats(o) ? (
              <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <Button variant="outline" size="icon-sm" disabled={busy || n === 0} onClick={() => set(o, n - 1)} aria-label={t('decision.fewer', 'One fewer')}>
                  <Minus />
                </Button>
                <span className="w-5 text-center font-semibold tabular-nums">{n}</span>
                <Button variant="outline" size="icon-sm" disabled={busy || chosen >= need} onClick={() => set(o, n + 1)} aria-label={t('decision.more', 'One more')}>
                  <Plus />
                </Button>
              </span>
            ) : (
              <span className={cn('grid size-5 place-items-center rounded border', n > 0 ? (discarding ? 'border-rose-500 bg-rose-500 text-white' : 'border-sky-500 bg-sky-500 text-white') : 'bg-white')}>
                {n > 0 && <Check className="size-3.5" />}
              </span>
            )}
          </div>
        )
      })}
      <div className="flex items-center gap-3 pt-1">
        <span className={cn('rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums', chosen === need ? 'bg-sky-500 text-white' : 'bg-muted text-foreground')}>
          {discarding ? t('decision.discardCount', 'Discard {count}/{need}', { count: chosen, need }) : t('decision.takeCount', 'Take {count}/{need}', { count: chosen, need })}
        </span>
        <Button disabled={busy || chosen !== need} onClick={confirm}>
          <Check /> {t('decision.confirm', 'Confirm')}
        </Button>
        {hints && (
          <span className="text-xs text-muted-foreground">
            {rule
              ? total > 1
                ? t('decision.oneByOne', 'One card at a time: {rest} more after this', { rest: total - 1 })
                : ''
              : t('decision.pickAny', 'Pick any {need}', { need })}
          </span>
        )}
      </div>
    </div>
  )
}

/** Map 4's harbour: once a building covers its space, any decision of your turn also offers to discard a
 *  hand card for 3 money (once per turn). Those options get this bar instead of mixing into the decision. */
function HarbourBar({
  options,
  cardsById,
  hints,
  bestIndex,
  busy,
  onMove,
}: {
  options: Option[]
  cardsById: Map<string, Card>
  hints: boolean
  bestIndex?: number
  busy: boolean
  onMove: (i: number) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-dashed border-violet-300 bg-violet-50/50 px-2.5 py-1.5 text-xs">
      <span className="font-semibold text-violet-800">{t('decision.harbour', 'Harbour')}</span>
      <span className="text-muted-foreground">{t('decision.harbourHint', 'Discard a hand card for 3 money (once per turn):')}</span>
      {options.map((o) => {
        const id = String(o.key[1])
        const top = hints && o.index === bestIndex
        return (
          <button
            key={o.index}
            type="button"
            disabled={busy}
            onClick={() => onMove(o.index)}
            title={o.label}
            className={cn('rounded-md border bg-white px-2 py-0.5 font-medium hover:border-violet-400 disabled:opacity-50', top && 'border-sky-500 ring-1 ring-sky-500')}
          >
            {cardsById.get(id)?.name ?? o.label}
            {hints && o.ai_prob !== undefined && <span className={cn('ml-1.5 text-[10px] font-normal tabular-nums', top ? 'font-semibold text-sky-700' : 'text-muted-foreground')}>{pct(o.ai_prob)}</span>}
            {top && <Sparkles className="ml-1 inline size-3 text-sky-600" />}
          </button>
        )
      })}
    </div>
  )
}

function OptionList({
  options,
  cardsById,
  hints,
  bestIndex,
  busy,
  onMove,
  onHoverOption,
}: {
  options: Option[]
  cardsById: Map<string, Card>
  hints: boolean
  bestIndex?: number
  busy: boolean
  onMove: (i: number) => void
  onHoverOption: (o: Option | null) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {options.map((o) => (
        <div
          key={o.index}
          role="button"
          tabIndex={busy ? -1 : 0}
          aria-disabled={busy || undefined}
          onMouseEnter={() => onHoverOption(o)}
          onMouseLeave={() => onHoverOption(null)}
          onClick={() => !busy && onMove(o.index)}
          onKeyDown={(e) => {
            if (!busy && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault()
              onMove(o.index)
            }
          }}
          className={cn(
            'flex cursor-pointer items-center gap-3 rounded-lg border bg-white px-3 py-2 text-sm transition hover:border-sky-400 hover:bg-sky-50/50',
            busy && 'cursor-wait opacity-60',
            hints && o.index === bestIndex && 'border-sky-500 ring-1 ring-sky-500',
          )}
        >
          <OptionIcon option={o} cardsById={cardsById} />
          <span className="flex-1">
            {o.label}
            {o.detail && <span className="mt-0.5 block text-xs text-muted-foreground">{o.detail}</span>}
          </span>
          {o.cards.length > 0 && (
            <span className="flex flex-wrap justify-end gap-1" onClick={(e) => e.stopPropagation()}>
              {o.cards.map((id) => (
                <CardChip key={id} id={id} card={cardsById.get(id)} />
              ))}
            </span>
          )}
          {hints && (
            <>
              {o.index === bestIndex && <Sparkles className="size-3.5 text-sky-600" aria-label={t('accessibility.aiFavorite', "AI's favourite")} />}
              <ProbBar p={o.ai_prob} best={o.index === bestIndex} />
            </>
          )}
        </div>
      ))}
    </div>
  )
}

function HunterChoice({
  cards,
  options,
  cardsById,
  hints,
  bestIndex,
  busy,
  onMove,
  onHoverOption,
}: {
  cards: Card[]
  options: Option[]
  cardsById: Map<string, Card>
  hints: boolean
  bestIndex?: number
  busy: boolean
  onMove: (i: number) => void
  onHoverOption: (o: Option | null) => void
}) {
  const takes = options.filter((o) => o.key[0] === 'take')
  const skip = options.find((o) => o.key[0] === 'skip')
  return (
    <div className="flex flex-col gap-1.5">
      {cards.map((card) => {
        const option = takes.find((o) => o.cards.includes(card.id))
        const selectable = !!option
        return (
          <div
            key={card.id}
            role={selectable ? 'button' : undefined}
            tabIndex={selectable && !busy ? 0 : undefined}
            aria-disabled={!selectable || busy || undefined}
            onMouseEnter={() => onHoverOption(option ?? null)}
            onMouseLeave={() => onHoverOption(null)}
            onClick={() => selectable && !busy && onMove(option.index)}
            onKeyDown={(e) => {
              if (selectable && !busy && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault()
                onMove(option.index)
              }
            }}
            className={cn(
              'flex items-center gap-3 rounded-lg border bg-white px-3 py-2 text-sm transition',
              selectable
                ? 'cursor-pointer hover:border-sky-400 hover:bg-sky-50/50'
                : 'cursor-not-allowed border-dashed opacity-55 grayscale-[0.35]',
              busy && 'cursor-wait opacity-60',
              hints && option?.index === bestIndex && 'border-sky-500 ring-1 ring-sky-500',
            )}
          >
            {option ? <OptionIcon option={option} cardsById={cardsById} /> : <span className="flex min-w-14 shrink-0 justify-center"><CardChip id={card.id} card={card} /></span>}
            <span className={cn('min-w-0 flex-1', !selectable && 'text-muted-foreground')}>
              {option ? option.label : t('decision.hunterNotAnimal', 'Not an animal, cannot take')}
            </span>
            {option && hints && (
              <>
                {option.index === bestIndex && <Sparkles className="size-3.5 text-sky-600" aria-label={t('accessibility.aiFavorite', "AI's favourite")} />}
                <ProbBar p={option.ai_prob} best={option.index === bestIndex} />
              </>
            )}
          </div>
        )
      })}
      {skip && (
        <div
          role="button"
          tabIndex={busy ? -1 : 0}
          aria-disabled={busy || undefined}
          onMouseEnter={() => onHoverOption(skip)}
          onMouseLeave={() => onHoverOption(null)}
          onClick={() => !busy && onMove(skip.index)}
          onKeyDown={(e) => {
            if (!busy && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault()
              onMove(skip.index)
            }
          }}
          className={cn(
            'flex cursor-pointer items-center gap-3 rounded-lg border border-dashed bg-white px-3 py-2 text-sm text-muted-foreground transition hover:border-sky-400 hover:bg-sky-50/50',
            busy && 'cursor-wait opacity-60',
            hints && skip.index === bestIndex && 'border-sky-500 ring-1 ring-sky-500',
          )}
        >
          <OptionIcon option={skip} cardsById={cardsById} />
          <span className="flex-1">{skip.label}</span>
          {hints && <ProbBar p={skip.ai_prob} best={skip.index === bestIndex} />}
        </div>
      )}
    </div>
  )
}

export function DecisionPanel(props: Props) {
  const { board, me, cardsById, hints, busy, group, groups, onGroup, onMove, onMoveMany, onHoverOption, reset, onDraft } = props
  const d = board.decision
  if (board.phase === 'end_turn' && !d) {
    return (
      <div className="bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
        {t('decision.yourTurnComplete', 'Your turn is complete. Press End turn (or Enter), or Undo to change it.')}
        {board.turn_log.length > 0 && (
          <ol className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-foreground">
            <span className="text-muted-foreground">{t('decision.youPlayed', 'You played:')}</span>
            {board.turn_log.map((line, i) => (
              <li key={i} className="rounded-md border bg-white px-1.5 py-0.5">
                {line}
              </li>
            ))}
          </ol>
        )}
        <div className="mt-2 grid grid-cols-5 gap-2 opacity-40 grayscale">
          {me.slots.map((sl, i) => (
            <div key={i} className="flex items-center gap-2 rounded-xl border-2 border-dashed px-2 py-1.5">
              <span className={cn('flex size-8 items-center justify-center rounded-lg text-lg font-bold text-white', ACTIONS[sl.action].color)}>{sl.strength}</span>
              <span className="text-sm font-semibold text-foreground">{ACTIONS[sl.action].label}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }
  if (!d) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        {board.over ? t('decision.gameOver', 'The game is over.') : t('decision.waitingForAi', 'Waiting for the AI...')}
      </div>
    )
  }
  // The harbour's discard (Map 4) can join any decision of your turn: it gets its own bar below, and the
  // panels see only the decision's own options.
  const harbour = d.options.filter((o) => o.type === 'harbor')
  const own = harbour.length > 0 ? { ...board, decision: { ...d, options: d.options.filter((o) => o.type !== 'harbor') } } : board
  const rest = own.decision!.options.filter((o) => o.type !== 'place')
  const placing = groups.length > 0

  return (
    <section className="flex flex-col gap-2 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">
          {d.title}
          {d.remaining != null && (
            <span className="ml-2 font-normal text-muted-foreground">
              {d.remaining === 1 ? t('decision.cardsLeftOne', '1 card to take') : t('decision.cardsLeft', '{count} cards to take', { count: d.remaining })}
            </span>
          )}
        </h2>
        {hints && d.ai && (
          <span className="flex items-center gap-1 text-xs text-sky-800">
            <Sparkles className="size-3.5" />{' '}
            {d.ai.rule
              ? t('decision.ruleHint', 'Rule policy suggestion')
              : t('decision.aiWinChance', 'AI estimates your win chance at {chance}', { chance: pct(d.ai.win_chance) })}
          </span>
        )}
      </div>

      {d.note && <p className="-mt-1 text-xs text-muted-foreground">{d.note}</p>}

      {d.kind === 'turn' ? (
        <TurnTiles key={`${board.records.length}-${reset}`} board={own} me={me} hints={hints} busy={busy} onMove={onMove} onDraft={onDraft} />
      ) : d.kind === 'setup_keep' ? (
        <SetupKeep key={`${board.seed}-${board.records.length}-${reset}`} board={own} cardsById={cardsById} hints={hints} busy={busy} onMove={onMove} onDraft={onDraft} />
      ) : (
        <>
          {placing && (
            <div className="space-y-2">
              {group ? (
                <div className="flex items-center gap-2 text-sm">
                  <Button variant="ghost" size="sm" onClick={() => onGroup(null)}>
                    <ArrowLeft /> {groups.length > 1 ? t('decision.otherBuildings', 'Other buildings') : t('decision.back', 'Back')}
                  </Button>
                  <span>
                    {t('decision.clickToPlace', 'Click a highlighted spot on the map to place the')}{' '}
                    <Tooltip>
                      <TooltipTrigger render={<b />} className="cursor-help underline decoration-dotted underline-offset-2">
                        {buildingStyle(group.building).label.toLowerCase()}
                        {t('decision.sizeParen', ' (size {size})', { size: group.size ?? '' })}
                      </TooltipTrigger>
                      <TooltipContent side="bottom" tone="light" className="max-w-72 px-3 py-2 leading-snug">{buildingEffect(group.building, group.size)}</TooltipContent>
                    </Tooltip>
                    . {t(group.options.length === 1 ? 'decision.placementsOne' : 'decision.placementsMany', group.options.length === 1 ? '{count} placement' : '{count} placements', { count: group.options.length })}.
                  </span>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {groups.map((g) => {
                    const total = g.options.reduce((s, o) => s + (o.ai_prob ?? 0), 0)
                    const top = g.options.some((o) => o.index === d.ai?.best) // holds the hint's favourite
                    return (
                      <Tooltip key={g.id}>
                        <TooltipTrigger
                          render={<button type="button" disabled={busy} onClick={() => onGroup(g.id)} />}
                          className="flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm transition hover:border-sky-400 hover:bg-sky-50/50 disabled:opacity-50"
                        >
                          <span className="size-3 rounded-sm" style={{ background: buildingStyle(g.building).fill }} />
                          <span className="font-medium">{buildingStyle(g.building).label}</span>
                          <span className="text-muted-foreground">{t('decision.size', 'size {size}', { size: g.size ?? '' })}</span>
                          {g.cost !== null && <Amount kind="money" n={g.cost} />}
                          {hints && top && <Sparkles className="size-3.5 text-sky-700" />}
                          {hints && <span className="text-xs text-sky-800 tabular-nums">{pct(total)}</span>}
                        </TooltipTrigger>
                        <TooltipContent side="bottom" tone="light" className="max-w-72 px-3 py-2 leading-snug">{buildingEffect(g.building, g.size)}</TooltipContent>
                      </Tooltip>
                    )
                  })}
                </div>
              )}
            </div>
          )}
          {rest.length > 0 && d.pick && d.pick.count > 1 && (
            <MultiPick
              key={`${board.seed}-${board.records.length}-${d.kind}-${reset}`}
              decision={own.decision!}
              options={rest}
              cardsById={cardsById}
              hints={hints}
              busy={busy}
              onConfirm={onMoveMany}
              onHoverOption={onHoverOption}
              onDraft={onDraft}
            />
          )}
          {rest.length > 0 && d.kind === 'ab_hunter' && d.revealed_cards && (
            <HunterChoice
              cards={d.revealed_cards}
              options={rest}
              cardsById={cardsById}
              hints={hints}
              bestIndex={d.ai?.best}
              busy={busy}
              onMove={onMove}
              onHoverOption={onHoverOption}
            />
          )}
          {rest.length > 0 && d.kind !== 'ab_hunter' && !(d.pick && d.pick.count > 1) && (
            <OptionList options={rest} cardsById={cardsById} hints={hints} bestIndex={d.ai?.best} busy={busy} onMove={onMove} onHoverOption={onHoverOption} />
          )}
        </>
      )}
      {harbour.length > 0 && <HarbourBar options={harbour} cardsById={cardsById} hints={hints} bestIndex={d.ai?.best} busy={busy} onMove={onMove} />}
    </section>
  )
}
