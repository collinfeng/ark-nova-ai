import { Award, Hand } from 'lucide-react'
import { GameIcon } from './GameIcon'

/** Small icon chips shared by the tracks panel and the decision options. */

export function Rep({ n }: { n: number }) {
  return (
    <span className="inline-flex items-center gap-px rounded-full bg-slate-500 px-1 text-[10px] leading-[1.3] font-bold text-white">
      <Award className="size-2.5" strokeWidth={2.8} />+{n}
    </span>
  )
}

/** What a university grants, drawn with icons: hand limit 5 and 1 reputation; 2 science; 1 science and 2 reputation. */
export function UniversityChip({ id, title }: { id: string; title: string }) {
  const science = <GameIcon name="science" size={14} />
  return (
    <span title={title} className="inline-flex items-center gap-0.5 rounded-md border bg-white px-1 py-0.5 text-foreground">
      {id === 'hand' && (
        <>
          <span className="inline-flex items-center gap-px text-[10px] font-bold">
            <Hand className="size-3" />5
          </span>
          <Rep n={1} />
        </>
      )}
      {id === 'science2' && (
        <>
          {science}
          {science}
        </>
      )}
      {id === 'science_rep' && (
        <>
          {science}
          <Rep n={2} />
        </>
      )}
      {!['hand', 'science2', 'science_rep'].includes(id) && title}
    </span>
  )
}

