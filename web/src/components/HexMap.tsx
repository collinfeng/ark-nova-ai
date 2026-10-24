import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { Building, Card, Cell, Option, Zoo } from '@/api/types'
import { buildingStyle, cellKey, pct } from '@/lib/game'
import { buildingEffect, gainText } from '@/lib/buildings'
import { t } from '@/i18n'
import { siteLabel, siteRule } from '@/lib/maps'
import { PrintedCard } from './CardTile'

const SQRT3 = Math.sqrt(3)
const TERRAIN_FILL: Record<string, string> = { plain: '#f1e6c6', water: '#bddaf0', rock: '#c9c8c4' }
/** A bonus space's mark: money and X-tokens with the same grey $ chip and hexagon as everywhere else, the rest in words. */
function BonusMark({ x, y, bonus }: { x: number; y: number; bonus: string }) {
  const money = { money2: 2, money5: 5, money10: 10 }[bonus]
  if (money !== undefined) {
    return (
      <g pointerEvents="none">
        <rect x={x - 0.36} y={y - 0.22} width={0.72} height={0.44} rx={0.1} fill="#5f6368" />
        <text x={x} y={y + 0.12} textAnchor="middle" fontWeight={800} fill="#fff">
          <tspan fontSize={0.22} fillOpacity={0.75}>$</tspan>
          <tspan fontSize={0.32}>{money}</tspan>
        </text>
      </g>
    )
  }
  if (bonus === 'xtoken') {
    const r = 0.26
    const pts = [0, 60, 120, 180, 240, 300].map((a) => `${x + r * Math.cos((a * Math.PI) / 180)},${y + r * Math.sin((a * Math.PI) / 180)}`).join(' ')
    return (
      <g pointerEvents="none">
        <polygon points={pts} fill="#334155" />
        <text x={x} y={y + 0.11} textAnchor="middle" fontSize={0.3} fontWeight={900} fill="#fff">X</text>
      </g>
    )
  }
  return (
    <text x={x} y={y + 0.12} textAnchor="middle" fontSize={0.4} fontWeight={600} fill="#7c5a10" pointerEvents="none">
      {bonusLabel(bonus)}
    </text>
  )
}

/** The short word printed on a bonus space of the map. */
function bonusLabel(bonus: string): string {
  switch (bonus) {
    case 'money5':
      return '$5'
    case 'money10':
      return '$10'
    case 'xtoken':
      return 'X'
    case 'card':
      return t('map.labelCard', 'card')
    case 'rep2':
      return t('map.labelRep', 'rep+2')
    case 'clever':
      return t('map.labelClever', 'clever')
    case 'rep1':
      return t('map.labelRepOne', 'rep+1')
    case 'kiosk':
      return t('map.labelKiosk', 'kiosk')
    case 'worker1':
      return t('map.labelWorker', 'worker')
    case 'partner_zoo':
      return t('map.labelPartnerZoo', 'partner')
    case 'university':
      return t('map.labelUniversity', 'univ.')
    case 'multiplier':
      return 'x2'
    case 'sponsor_for_money':
      return t('map.labelSponsor', 'sponsor')
    default:
      return bonus
  }
}
const KIND_SHORT: Record<string, string> = {
  kiosk: 'K',
  pavilion: 'P',
  petting_zoo: 'Pet',
  reptile_house: 'RH',
  aviary: 'Av',
}

function abbreviate(name: string): string {
  const words = name.replace(/[^A-Za-z ]/g, '').split(/\s+/).filter(Boolean)
  const letters = words.length > 1 ? words.map((w) => w[0]).join('') : name.slice(0, 3)
  return letters.slice(0, 3).toUpperCase()
}

function buildingLabel(b: Building, cardName: string): string {
  if (b.kind === 'unique') return abbreviate(cardName || 'Spo')
  // Map 2: an enclosure next to the outdoor area counts as larger (capacity), shown as E3+2.
  if (b.kind === 'enclosure') return b.capacity > b.size ? `E${b.size}+${b.capacity - b.size}` : `E${b.size}`
  return KIND_SHORT[b.kind] ?? b.kind.slice(0, 2)
}

function hexPoints(x: number, y: number, r = 1): string {
  const pts: string[] = []
  for (let k = 0; k < 6; k++) {
    const a = (Math.PI / 3) * k
    pts.push(`${(x + r * Math.cos(a)).toFixed(3)},${(y + r * Math.sin(a)).toFixed(3)}`)
  }
  return pts.join(' ')
}

/** Edges of a cell group that border a cell outside the group (flat-top hexes). */
function outlineEdges(cells: Cell[], inGroup: (c: Cell) => boolean, all: Cell[]): [number, number, number, number][] {
  const edges: [number, number, number, number][] = []
  for (const c of cells) {
    for (let k = 0; k < 6; k++) {
      const na = (Math.PI / 3) * k + Math.PI / 6
      const nx = c.x + SQRT3 * Math.cos(na)
      const ny = c.y + SQRT3 * Math.sin(na)
      const nb = all.find((o) => Math.abs(o.x - nx) < 0.3 && Math.abs(o.y - ny) < 0.3)
      if (nb && inGroup(nb)) continue
      const a1 = (Math.PI / 3) * k
      const a2 = (Math.PI / 3) * (k + 1)
      edges.push([c.x + Math.cos(a1), c.y + Math.sin(a1), c.x + Math.cos(a2), c.y + Math.sin(a2)])
    }
  }
  return edges
}

export interface Placement {
  options: Option[]
  hints: boolean
  disabled: boolean
  onPick: (index: number) => void
}

interface HexMapProps {
  zoo: Zoo
  cardsById: Map<string, Card>
  highlightBuilding?: number | null
  placement?: Placement
}

function bonusText(bonus: string): string {
  switch (bonus) {
    case 'card':
      return t('map.coveredBonus', 'Covering this space: take 1 card from the deck or a display folder in reputation range.')
    case 'money5':
      return t('map.moneyFive', 'Covering this space: gain 5 money.')
    case 'money10':
      return t('map.moneyTen', 'Covering this space: gain 10 money.')
    case 'xtoken':
      return t('map.xToken', 'Covering this space: gain 1 X-token.')
    case 'rep2':
      return t('map.reputationTwo', 'Covering this space: gain 2 reputation.')
    case 'clever':
      return t('map.clever', 'Covering this space: you may move one of your action cards to slot 1.')
    case 'money2':
      return t('map.moneyTwo', 'Covering this space: gain 2 money.')
    case 'rep1':
      return t('map.reputationOne', 'Covering this space: gain 1 reputation.')
    case 'kiosk':
      return t('map.freeKiosk', 'Covering this space: place a kiosk for free.')
    case 'worker1':
      return t('map.worker', 'Covering this space: gain 1 association worker.')
    case 'partner_zoo':
      return t('map.partnerZoo', 'Covering this space: take a partner zoo.')
    case 'university':
      return t('map.university', 'Covering this space: take a university.')
    case 'multiplier':
      return t('map.multiplier', 'Covering this space: put the x2 token on one of your action cards.')
    case 'sponsor_for_money':
      return t('map.sponsorForMoney', 'Covering this space: you may play a sponsor card from your hand, paying its level in money.')
    default:
      return t('map.bonus', 'Bonus: {bonus}', { bonus })
  }
}

function cellInfo(c: Cell): string[] {
  const out: string[] = []
  if (c.site) out.push(siteRule(c.site))
  if (c.bonus && c.building === null) out.push(bonusText(c.bonus))
  if (c.build2) out.push(t('map.buildTwoRule', 'Only buildable with Build II.'))
  if (c.terrain === 'water') out.push(t('map.waterRuleLong', "Water: can't be built on; animals needing water want it next to their enclosure."))
  if (c.terrain === 'rock') out.push(t('map.rockRuleLong', "Rock: can't be built on; animals needing rock want it next to their enclosure."))
  return out
}

function infoText(b: Building): string | null {
  switch (b.kind) {
    case 'kiosk':
    case 'pavilion':
    case 'petting_zoo':
    case 'reptile_house':
    case 'aviary':
      return `${buildingStyle(b.kind).label}: ${buildingEffect(b.kind, b.size)}`
    case 'unique':
      return b.sponsor_card ? null : buildingEffect(b.kind)
    case 'enclosure':
      if (b.animals.length > 0) return null
      return b.capacity > b.size
        ? t('map.emptyEnclosureOutdoor', 'Enclosure size {size}, empty. Next to the outdoor area it counts as size {capacity}: houses one animal of size ≤ {capacity} (with its rock/water needs next to it).', { size: b.size, capacity: b.capacity })
        : t('map.emptyEnclosure', 'Enclosure size {size}, empty: houses one animal of size ≤ {size} (with its rock/water needs next to it).', { size: b.size })
    default:
      return null
  }
}

type Pop = { x: number; y: number; building?: Building; lines?: string[] }

function MapPopup({ pop }: { pop: Pop }) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    let left = pop.x + 28
    if (left + r.width > innerWidth - 8) left = pop.x - r.width - 28
    left = Math.max(8, left)
    const top = Math.max(8, Math.min(pop.y - r.height / 2, innerHeight - r.height - 8))
    setPos({ left, top })
  }, [pop])
  const b = pop.building
  const cards = b ? [...(b.animal_cards ?? []), ...(b.sponsor_card ? [b.sponsor_card] : [])] : []
  const info = b ? infoText(b) : null
  const header = b ? (b.kind === 'enclosure' ? (cards.length > 0 ? t('map.occupiedEnclosure', 'Enclosure size {size}, occupied', { size: b.size }) : null) : b.kind === 'unique' ? null : specialKind(b.kind) ? t('map.buildingUsed', '{name}: {used}/{capacity} spaces used', { name: buildingStyle(b.kind).label, used: b.used, capacity: b.capacity }) : null) : null
  return createPortal(
    <div ref={ref} className={`pointer-events-none fixed z-50 rounded-xl bg-popover p-2 shadow-xl ring-1 ring-foreground/15 ${pos ? '' : 'invisible'}`} style={{ left: pos?.left ?? 0, top: pos?.top ?? 0 }}>
      {header && <div className="mb-1 text-xs font-semibold">{header}</div>}
      {cards.length > 0 && (
        <div className="flex gap-2" style={{ zoom: 1.2 }}>
          {cards.map((c) => (
            <PrintedCard key={c.id} card={c} variant="detail" status={null} />
          ))}
        </div>
      )}
      {cards.length === 0 && (info || b) && <p className="max-w-64 text-sm">{info ?? (b ? buildingTitle2(b) : '')}</p>}
      {cards.length > 0 && info && b && specialKind(b.kind) && <p className="mt-1 max-w-80 text-xs text-muted-foreground">{buildingEffect(b.kind, b.size)}</p>}
      {pop.lines?.map((l, i) => (
        <p key={i} className="max-w-64 text-sm">
          {l}
        </p>
      ))}
    </div>,
    document.body,
  )
}

const specialKind = (k: string) => k === 'petting_zoo' || k === 'reptile_house' || k === 'aviary'

function buildingTitle2(b: Building): string {
  const name = buildingStyle(b.kind).label
  if (b.kind === 'unique') return name
  if (specialKind(b.kind)) return `${t('map.buildingSpaces', '{name}, size {size}: {used}/{capacity} spaces used', { name, size: b.size, used: b.used, capacity: b.capacity })}${b.animals.length ? ` (${b.animals.join(t('common.listSep', ', '))})` : ''}`
  return t('map.buildingSize', '{name}, size {size}', { name, size: b.size })
}

export function HexMap({ zoo, cardsById, highlightBuilding, placement }: HexMapProps) {
  const emptyPatternId = `empty-habitat-${useId().replace(/:/g, '')}`
  const [hoverBuilding, setHoverBuilding] = useState<Building | null>(null)
  // Placement: the hovered candidate hex and which of the placements covering it is shown.
  const [hoverCell, setHoverCell] = useState<string | null>(null)
  const [turn, setTurn] = useState(0)
  const svgRef = useRef<SVGSVGElement>(null)
  const [pop, setPop] = useState<Pop | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const arm = (e: React.PointerEvent, p: Omit<Pop, 'x' | 'y'>) => {
    window.clearTimeout(timer.current)
    if (placement) return
    const x = e.clientX
    const y = e.clientY
    timer.current = window.setTimeout(() => setPop({ x, y, ...p }), 300)
  }
  const disarm = () => {
    window.clearTimeout(timer.current)
    setPop(null)
  }
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const byKey = useMemo(() => new Map(zoo.cells.map((c) => [cellKey(c.q, c.r), c])), [zoo.cells])

  const { viewBox, outlines } = useMemo(() => {
    const xs = zoo.cells.map((c) => c.x)
    const ys = zoo.cells.map((c) => c.y)
    const minX = Math.min(...xs) - 1.02
    const minY = Math.min(...ys) - 0.95
    const w = Math.max(...xs) + 1.02 - minX
    const h = Math.max(...ys) + 0.95 - minY
    const outlines = zoo.buildings.map((b) => {
      const cs = b.cells.map(([q, r]) => byKey.get(cellKey(q, r))).filter((c): c is Cell => !!c)
      const set = new Set(cs)
      return { b, cs, edges: outlineEdges(cs, (c) => set.has(c), zoo.cells) }
    })
    return { viewBox: `${minX} ${minY} ${w} ${h}`, outlines }
  }, [zoo, byKey])

  const candidates = useMemo(() => placement?.options ?? [], [placement?.options])
  const hints = !!placement?.hints
  // Every placement covering each hex, the AI's favourite first when hints are on.
  const reach = useMemo(() => {
    const m = new Map<string, Option[]>()
    for (const o of candidates) for (const [q, r] of o.cells ?? []) m.set(cellKey(q, r), [...(m.get(cellKey(q, r)) ?? []), o])
    if (hints) for (const list of m.values()) list.sort((a, b) => (b.ai_prob ?? 0) - (a.ai_prob ?? 0))
    return m
  }, [candidates, hints])
  const here = hoverCell ? (reach.get(hoverCell) ?? []) : []
  const hovered = here.length ? here[((turn % here.length) + here.length) % here.length] : undefined
  const many = here.length > 1
  const cycle = useCallback((d: number) => setTurn((t) => t + d), [])
  useEffect(() => {
    const svg = svgRef.current
    if (!svg || !many) return
    const wheel = (e: WheelEvent) => {
      e.preventDefault()  // rotate instead of scrolling the column
      cycle(e.deltaY > 0 ? 1 : -1)
    }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'r' || e.key === 'R') cycle(e.shiftKey ? -1 : 1)
    }
    svg.addEventListener('wheel', wheel, { passive: false })
    window.addEventListener('keydown', key)
    return () => {
      svg.removeEventListener('wheel', wheel)
      window.removeEventListener('keydown', key)
    }
  }, [many, cycle])
  const union = useMemo(() => [...reach.keys()].map((k) => byKey.get(k)).filter((c): c is Cell => !!c), [reach, byKey])
  // With AI hints: the AI's favourite placement gets an outline and the only standing label; the others
  // show their share while hovered, so labels of overlapping placements never pile up.
  const best = placement?.hints
    ? candidates.reduce<Option | undefined>((b, o) => ((o.ai_prob ?? 0) > (b?.ai_prob ?? 0) ? o : b), undefined)
    : undefined
  const footprint = (o: Option) => (o.cells ?? []).map(([q, r]) => byKey.get(cellKey(q, r))).filter((c): c is Cell => !!c)
  const centre = (cells: Cell[]) => ({ x: cells.reduce((s, c) => s + c.x, 0) / cells.length, y: cells.reduce((s, c) => s + c.y, 0) / cells.length })
  const tag = (o: Option, star: boolean) => {
    const cells = footprint(o)
    if (!cells.length || o.ai_prob === undefined) return null
    const { x, y } = centre(cells)
    const text = `${star ? '★ ' : ''}${pct(o.ai_prob)}`
    const w = 0.3 * text.length + 0.3
    return (
      <g pointerEvents="none">
        <rect x={x - w / 2} y={y - 0.34} width={w} height={0.62} rx={0.31} fill="white" fillOpacity={0.92} stroke={star ? '#b45309' : '#0369a1'} strokeWidth={0.05} />
        <text x={x} y={y + 0.13} textAnchor="middle" fontSize={0.42} fontWeight={800} fill={star ? '#92400e' : '#0c4a6e'}>
          {text}
        </text>
      </g>
    )
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <svg ref={svgRef} viewBox={viewBox} preserveAspectRatio="xMidYMid meet" className="mx-auto block min-h-0 w-full flex-1" role="img" aria-label={t('map.zooMap', 'Zoo map')}>
        <defs>
          <pattern id={emptyPatternId} width={0.32} height={0.32} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width={0.32} height={0.32} fill="#f1f3f5" />
            <rect width={0.11} height={0.32} fill="#d1d5db" />
          </pattern>
        </defs>
        {zoo.cells.map((c) => (
          <g
            key={cellKey(c.q, c.r)}
            onPointerEnter={(e) => {
              const lines = cellInfo(c)
              if (lines.length) arm(e, { lines })
            }}
            onPointerLeave={disarm}
          >
            <polygon points={hexPoints(c.x, c.y, 0.98)} fill={TERRAIN_FILL[c.terrain] ?? '#eee'} stroke="#fff" strokeWidth={0.06} />
            {c.build2 && (
              <polygon points={hexPoints(c.x, c.y, 0.98)} fill="#e0584a" fillOpacity={0.28} stroke="#b42318" strokeWidth={0.1} />
            )}
          </g>
        ))}
        {outlines.map(({ b, cs, edges }) => {
          const style = buildingStyle(b.kind)
          const cx = cs.reduce((s, c) => s + c.x, 0) / (cs.length || 1)
          const cy = cs.reduce((s, c) => s + c.y, 0) / (cs.length || 1)
          const hl = highlightBuilding === b.id || hoverBuilding?.id === b.id
          const empty = (b.kind === 'enclosure' || specialKind(b.kind)) && b.animals.length === 0
          const unique = b.kind === 'unique' ? (cardsById.get(b.name ?? '')?.name ?? '') : ''
          return (
            <g
              key={b.id}
              onMouseEnter={() => setHoverBuilding(b)}
              onMouseLeave={() => setHoverBuilding(null)}
              onPointerEnter={(e) => arm(e, { building: b })}
              onPointerLeave={disarm}
            >
              {cs.map((c) => (
                <polygon key={cellKey(c.q, c.r)} points={hexPoints(c.x, c.y, 0.98)} fill={empty ? `url(#${emptyPatternId})` : style.fill} opacity={hl || empty ? 1 : 0.92} />
              ))}
              {edges.map((e, i) => (
                <line key={i} x1={e[0]} y1={e[1]} x2={e[2]} y2={e[3]} stroke={empty ? (hl ? '#166534' : '#34865a') : (hl ? '#111827' : '#374151')} strokeWidth={hl ? 0.16 : 0.1} strokeLinecap="round" />
              ))}
              {(() => {
                const lc = cs.reduce((best, c) => (Math.hypot(c.x - cx, c.y - cy) < Math.hypot(best.x - cx, best.y - cy) ? c : best), cs[0])
                if (!lc) return null
                const label = buildingLabel(b, unique)
                const fs = label.length >= 3 ? 0.46 : 0.6
                return (
                  <>
                    <text x={lc.x} y={lc.y + fs * 0.35} textAnchor="middle" fontSize={fs} fontWeight={700} fill="#1f2937" pointerEvents="none">
                      {label}
                    </text>
                    {b.kind !== 'kiosk' && b.kind !== 'pavilion' &&
                      (b.animals.length > 0
                        ? Array.from({ length: Math.max(b.used, 1) }, (_, i) => (
                            // one dot per space used (an animal can take several, or none), from the upper right towards the left
                            <circle key={i} cx={lc.x + 0.55 - i * 0.3} cy={lc.y - 0.55} r={0.13} fill={b.used > 0 ? '#7c2d12' : '#fff'} stroke={b.used > 0 ? '#fff' : '#7c2d12'} strokeWidth={0.05} pointerEvents="none" />
                          ))
                        : b.kind === 'unique' && <circle cx={lc.x + 0.55} cy={lc.y - 0.55} r={0.17} fill="#1e3a8a" stroke="#fff" strokeWidth={0.05} pointerEvents="none" />)}
                  </>
                )
              })()}
            </g>
          )
        })}
        {zoo.cells
          .filter((c) => c.bonus && c.building === null)
          .map((c) => (
            <BonusMark key={cellKey(c.q, c.r)} x={c.x} y={c.y} bonus={c.bonus!} />
          ))}
        {zoo.cells
          .filter((c) => c.build2)
          .map((c) => (
            <text key={cellKey(c.q, c.r)} x={c.x} y={c.y - 0.45} textAnchor="middle" fontSize={0.36} fontWeight={700} fill="#b42318" pointerEvents="none">
              II
            </text>
          ))}
        {zoo.cells
          .filter((c) => c.site)
          .map((c) => {
            const covered = c.building !== null
            const word = siteLabel(c.site!)
            const big = word.length <= 2
            // Under a bonus mark the word goes to the bottom of the space; on its own it takes the centre.
            const y = c.bonus && !covered ? c.y + 0.62 : c.y + (big ? 0.2 : 0.12)
            return (
              <g key={`site-${cellKey(c.q, c.r)}`} pointerEvents="none">
                <polygon points={hexPoints(c.x, c.y, 0.84)} fill="none" stroke="#7c3aed" strokeWidth={0.08} strokeDasharray="0.18 0.12" />
                {!covered && (
                  <text x={c.x} y={y} textAnchor="middle" fontSize={big ? 0.6 : word.length > 7 ? 0.27 : 0.32} fontWeight={800} fill="#6d28d9">
                    {word}
                  </text>
                )}
              </g>
            )
          })}
        {union.map((c) => {
          const k = cellKey(c.q, c.r)
          return (
            <polygon
              key={`cand-${k}`}
              points={hexPoints(c.x, c.y, 0.94)}
              fill="#38bdf8"
              fillOpacity={0.32}
              stroke="#0369a1"
              strokeWidth={0.07}
              className={placement?.disabled ? 'cursor-wait' : 'cursor-pointer'}
              onPointerEnter={() => {
                setHoverCell(k)
                setTurn(0)
              }}
              onPointerLeave={() => setHoverCell((h) => (h === k ? null : h))}
              onClick={() => hovered && !placement?.disabled && placement?.onPick(hovered.index)}
              onContextMenu={(e) => {
                e.preventDefault()
                if (many) cycle(1)
              }}
            />
          )
        })}
        {hovered &&
          (() => {
            const cells = footprint(hovered)
            const set = new Set(cells)
            return (
              <g pointerEvents="none">
                {cells.map((c) => (
                  <polygon key={cellKey(c.q, c.r)} points={hexPoints(c.x, c.y, 0.94)} fill="#0ea5e9" fillOpacity={0.75} />
                ))}
                {outlineEdges(cells, (c) => set.has(c), zoo.cells).map((e, i) => (
                  <line key={i} x1={e[0]} y1={e[1]} x2={e[2]} y2={e[3]} stroke="#075985" strokeWidth={0.16} strokeLinecap="round" />
                ))}
              </g>
            )
          })()}
        {best &&
          (() => {
            const cells = footprint(best)
            const set = new Set(cells)
            return outlineEdges(cells, (c) => set.has(c), zoo.cells).map((e, i) => (
              <line key={`best-${i}`} x1={e[0]} y1={e[1]} x2={e[2]} y2={e[3]} stroke="#d97706" strokeWidth={0.2} strokeLinecap="round" pointerEvents="none" />
            ))
          })()}
        {best && tag(best, true)}
        {hints && hovered && hovered !== best && tag(hovered, false)}
      </svg>
      {pop && <MapPopup pop={pop} />}
      {hovered && (
        <div className="pointer-events-none absolute bottom-1 left-1/2 w-max max-w-[95%] -translate-x-1/2 rounded-lg bg-slate-800/90 px-3 py-1 text-center text-xs text-white shadow">
          <b>{buildingStyle(hovered.building ?? 'unique').label}</b>
          {': '}
          {hovered.gains?.length ? hovered.gains.map(gainText).join(' · ') : t('map.nothingExtra', 'no bonus here')}
          {many && (
            <>
              {' · '}
              <b className="tabular-nums">
                {((turn % here.length) + here.length) % here.length + 1}/{here.length}
              </b>{' '}
              {t('map.orientationsLine', 'orientations: scroll, R or right-click to rotate')}
            </>
          )}
        </div>
      )}
    </div>
  )
}
