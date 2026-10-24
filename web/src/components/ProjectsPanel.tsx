import { Ban } from 'lucide-react'
import type { Project } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { CardChip, ProjectSlots, projectCategory } from './CardTile'
import { GameIcon } from './GameIcon'
import { RichText } from './Rich'
import { Tip } from './TracksPanel'

function Token({ v, humanIdx }: { v: number | 'blocked' | undefined; humanIdx: number }) {
  if (v === undefined) {
    return <span className="size-4 shrink-0 rounded-full border border-dashed border-slate-300 bg-white" title={t('projects.free', 'Free')} />
  }
  if (v === 'blocked') {
    return (
      <span className="grid size-4 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-400" title={t('projects.blocked', 'Blocked')}>
        <Ban className="size-3" aria-label={t('projects.blocked', 'Blocked')} />
      </span>
    )
  }
  const you = v === humanIdx
  return (
    <span
      className={cn('flex size-4 shrink-0 items-center justify-center rounded-full text-[8px] font-bold text-white shadow-sm ring-2 ring-white', you ? 'bg-sky-500' : 'bg-orange-500')}
      title={you ? t('projects.supportedByYou', 'Your token') : t('projects.supportedByAi', "AI's token")}
    >
      {you ? 'Y' : 'A'}
    </span>
  )
}

export function ProjectsPanel({ projects, humanIdx }: { projects: Project[]; humanIdx: number }) {
  const tokens = projects.flatMap((p) => Object.values(p.tokens))
  const yours = tokens.filter((v) => v === humanIdx).length
  const ai = tokens.filter((v) => typeof v === 'number' && v !== humanIdx).length

  return (
    <div className="space-y-2 p-2">
      <div className="flex items-center gap-2 rounded-lg bg-emerald-50/80 px-2.5 py-2 text-[11px]">
        <span className="font-semibold text-emerald-950">{t('projects.available', '{count} projects', { count: projects.length })}</span>
        <span className="ml-auto flex items-center gap-1 text-sky-800">
          <i className="size-2 rounded-full bg-sky-500" /> {t('projects.yoursShort', 'You {count}', { count: yours })}
        </span>
        <span className="flex items-center gap-1 text-orange-800">
          <i className="size-2 rounded-full bg-orange-500" /> {t('projects.aiShort', 'AI {count}', { count: ai })}
        </span>
      </div>
      {projects.map((p) => (
        <section key={p.card.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
          <div className="flex items-center gap-2 border-b border-emerald-100 bg-emerald-50/55 px-2 py-1.5">
            {p.card.icon && (
              <Tip tip={p.card.text[0] ? <RichText text={p.card.text[0]} /> : p.card.name} className="grid size-6 shrink-0 cursor-help place-items-center rounded-full bg-white ring-1 ring-emerald-900/10">
                <GameIcon name={p.card.icon} size={16} />
              </Tip>
            )}
            <CardChip id={p.card.id} card={p.card} />
            <span className="flex-1" />
            <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-bold text-emerald-900">
              {p.base ? t('projects.base', 'base') : projectCategory(p.card.category)}
            </span>
          </div>
          <div className="px-2.5 py-1.5">
            <ProjectSlots layout="row" card={p.card} marker={(pos) => <Token v={p.tokens[String(pos)]} humanIdx={humanIdx} />} />
          </div>
        </section>
      ))}
    </div>
  )
}
