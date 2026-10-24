import { useState } from 'react'
import { ChevronDown, ChevronUp, Flag, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import type { FeedLine } from '@/api/types'
import { isResource, ResourceIcon } from './Resource'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

/** The icon of what changed; the same marks as the player panel. */
function KindIcon({ kind }: { kind: string }) {
  return isResource(kind) ? <ResourceIcon kind={kind} /> : <Info className="size-3.5 shrink-0 text-muted-foreground" />
}

/** "+3 money", "-2 X-tokens"; cards and upgrades are things you get to do, so no sign for those. */
function amountText(line: Extract<FeedLine, { kind: string }>) {
  const counted = ['money', 'appeal', 'conservation', 'reputation', 'xtoken', 'worker'].includes(line.kind)
  return counted ? `${line.amount > 0 ? '+' : '−'}${line.text}` : line.text
}

function who(w: 'you' | 'ai') {
  return w === 'you' ? t('feed.you', 'You') : t('feed.ai', 'AI')
}

function Row({ line, withWho }: { line: FeedLine; withWho: boolean }) {
  if ('note' in line) {
    const brk = line.note === 'break'
    return (
      <li className={cn('flex items-start gap-1.5 rounded-md px-2 py-1 text-xs', brk ? 'bg-amber-100 font-medium text-amber-950' : 'text-muted-foreground')}>
        {brk ? <Flag className="mt-px size-3.5 shrink-0 text-amber-600" /> : <Info className="mt-px size-3.5 shrink-0" />}
        <span>{line.text}</span>
      </li>
    )
  }
  const loss = line.amount < 0
  return (
    <li className="flex items-center gap-1.5 px-2 py-0.5 text-xs">
      {withWho && <span className={cn('w-8 shrink-0 text-[10px] font-semibold', line.who === 'you' ? 'text-sky-700' : 'text-orange-700')}>{who(line.who)}</span>}
      <KindIcon kind={line.kind} />
      <span className={cn('shrink-0 font-semibold tabular-nums', loss ? 'text-rose-700' : 'text-emerald-700')}>{amountText(line)}</span>
      {line.why && <span className="min-w-0 truncate text-muted-foreground" title={line.why}>{line.why}</span>}
    </li>
  )
}

/** What your moves this turn gained and spent, and why, in the action zone. The last few lines show;
 *  the rest open on request. A break is picked out. */
export function TurnFeed({ lines }: { lines: FeedLine[] }) {
  const [open, setOpen] = useState(false)
  if (lines.length === 0) return null
  // The break track ticking up is noise next to real changes, unless it is all there is.
  const shown = lines.filter((l) => !('note' in l && l.note === 'info' && /\d+\/\d+/.test(l.text)) || lines.length === 1)
  const LIMIT = 5
  const visible = open ? shown : shown.slice(-LIMIT)
  return (
    <section className="border-b bg-slate-50/70 px-2 py-1.5">
      <div className="mb-0.5 flex items-center justify-between px-1 text-[11px] font-semibold text-muted-foreground">
        <span>{t('feed.title', 'This turn so far')}</span>
        {shown.length > LIMIT && (
          <button type="button" onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-0.5 font-normal hover:text-foreground">
            {open ? t('feed.showLess', 'Show less') : t('feed.showAll', 'Show all {count}', { count: shown.length })}
            {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
          </button>
        )}
      </div>
      <ul className="space-y-px">
        {visible.map((l, i) => (
          <Row key={i} line={l} withWho={false} />
        ))}
      </ul>
    </section>
  )
}

/** The changes of one AI move as small chips, for the AI box; the reason is in the tooltip. */
export function FeedChips({ lines }: { lines: FeedLine[] }): ReactNode {
  const changes = lines.filter((l): l is Extract<FeedLine, { kind: string }> => 'kind' in l)
  const breaks = lines.filter((l) => 'note' in l && l.note === 'break')
  if (changes.length === 0 && breaks.length === 0) return null
  return (
    <span className="mt-px flex flex-wrap gap-1">
      {breaks.length > 0 && (
        <span className="inline-flex items-center gap-0.5 rounded bg-amber-100 px-1 text-[10px] font-medium text-amber-950">
          <Flag className="size-2.5" /> {t('feed.break', 'Break')}
        </span>
      )}
      {changes.map((l, i) => (
        <span key={i} title={l.why ?? undefined} className="inline-flex items-center gap-0.5 rounded bg-white/70 px-1 text-[10px] tabular-nums">
          <span className={cn('font-semibold', l.who === 'you' && 'text-sky-700')}>{l.who === 'you' ? `${who('you')} ` : ''}</span>
          <KindIcon kind={l.kind} />
          <span className={cn('font-semibold', l.amount < 0 ? 'text-rose-700' : 'text-emerald-700')}>{amountText(l)}</span>
        </span>
      ))}
    </span>
  )
}
