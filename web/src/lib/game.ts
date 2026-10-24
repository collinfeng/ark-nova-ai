import {
  Banana,
  Bird,
  Cat,
  Droplet,
  FlaskConical,
  Heart,
  Leaf,
  Mountain,
  PawPrint,
  Worm,
  type LucideIcon,
} from 'lucide-react'
import type { ActionName, Board, BuildingKind, Card, Option, Player } from '@/api/types'
import { t, term } from '@/i18n'

export const ACTIONS: Record<ActionName, { label: string; blurb: string; color: string; tint: string }> = {
  animals: { get label() { return term('actions', 'animals', 'Animals') }, get blurb() { return t('actionBlurb.animals', 'Play animal cards into your zoo') }, color: 'bg-emerald-600', tint: 'border-emerald-300 bg-emerald-50' },
  build: { get label() { return term('actions', 'build', 'Build') }, get blurb() { return t('actionBlurb.build', 'Place buildings on your map') }, color: 'bg-amber-600', tint: 'border-amber-300 bg-amber-50' },
  cards: { get label() { return term('actions', 'cards', 'Cards') }, get blurb() { return t('actionBlurb.cards', 'Draw or snap cards') }, color: 'bg-sky-600', tint: 'border-sky-300 bg-sky-50' },
  association: { get label() { return term('actions', 'association', 'Association') }, get blurb() { return t('actionBlurb.association', 'Conservation projects and partners') }, color: 'bg-violet-600', tint: 'border-violet-300 bg-violet-50' },
  sponsors: { get label() { return term('actions', 'sponsors', 'Sponsors') }, get blurb() { return t('actionBlurb.sponsors', 'Play sponsor cards, gain money') }, color: 'bg-rose-600', tint: 'border-rose-300 bg-rose-50' },
}

export const CARD_TYPE: Record<string, { label: string; stripe: string; chip: string }> = {
  animal: { get label() { return term('cardTypes', 'animal', 'Animal') }, stripe: 'bg-emerald-500', chip: 'bg-emerald-100 text-emerald-800' },
  sponsor: { get label() { return term('cardTypes', 'sponsor', 'Sponsor') }, stripe: 'bg-rose-500', chip: 'bg-rose-100 text-rose-800' },
  project: { get label() { return term('cardTypes', 'project', 'Project') }, stripe: 'bg-violet-500', chip: 'bg-violet-100 text-violet-800' },
  endgame: { get label() { return term('cardTypes', 'endgame', 'Final scoring') }, stripe: 'bg-amber-500', chip: 'bg-amber-100 text-amber-800' },
}

export const BUILDING_STYLE: Record<string, { fill: string; label: string }> = {
  enclosure: { fill: '#86b98f', get label() { return term('buildings', 'enclosure', 'Enclosure') } },
  kiosk: { fill: '#e8a85a', get label() { return term('buildings', 'kiosk', 'Kiosk') } },
  pavilion: { fill: '#e07f8a', get label() { return term('buildings', 'pavilion', 'Pavilion') } },
  petting_zoo: { fill: '#c9a0dc', get label() { return term('buildings', 'petting_zoo', 'Petting zoo') } },
  reptile_house: { fill: '#9cc06b', get label() { return term('buildings', 'reptile_house', 'Reptile house') } },
  aviary: { fill: '#74bde0', get label() { return term('buildings', 'aviary', 'Aviary') } },
  unique: { fill: '#8f9bd6', get label() { return term('buildings', 'unique', 'Sponsor building') } },
}

export function buildingStyle(kind: BuildingKind | string) {
  return BUILDING_STYLE[kind] ?? { fill: '#b8b8b8', label: kind }
}

export interface IconMeta {
  key: string
  label: string
  color: string
  /** Lucide glyph, or fall back to the short letters. */
  glyph?: LucideIcon
  short: string
}

export const ICON_META: Record<string, IconMeta> = {
  africa: { key: 'africa', get label() { return term('icons', 'africa', 'Africa') }, color: '#f5d020', short: 'Af' },
  americas: { key: 'americas', get label() { return term('icons', 'americas', 'Americas') }, color: '#f6b27a', short: 'Am' },
  asia: { key: 'asia', get label() { return term('icons', 'asia', 'Asia') }, color: '#9fd3a8', short: 'As' },
  australia: { key: 'australia', get label() { return term('icons', 'australia', 'Australia') }, color: '#e85a50', short: 'Au' },
  europe: { key: 'europe', get label() { return term('icons', 'europe', 'Europe') }, color: '#8cc2ef', short: 'Eu' },
  bird: { key: 'bird', get label() { return term('icons', 'bird', 'Bird') }, color: '#2aa3e0', glyph: Bird, short: 'Bi' },
  predator: { key: 'predator', get label() { return term('icons', 'predator', 'Predator') }, color: '#b0302e', glyph: Cat, short: 'Pr' },
  herbivore: { key: 'herbivore', get label() { return term('icons', 'herbivore', 'Herbivore') }, color: '#2f7d3c', glyph: Leaf, short: 'He' },
  reptile: { key: 'reptile', get label() { return term('icons', 'reptile', 'Reptile') }, color: '#7449a6', glyph: Worm, short: 'Re' },
  primate: { key: 'primate', get label() { return term('icons', 'primate', 'Primate') }, color: '#e3a21a', glyph: Banana, short: 'Pm' },
  bear: { key: 'bear', get label() { return term('icons', 'bear', 'Bear') }, color: '#7a4e2d', glyph: PawPrint, short: 'Be' },
  pet: { key: 'pet', get label() { return term('icons', 'pet', 'Petting zoo animal') }, color: '#d9719a', glyph: Heart, short: 'Pe' },
  science: { key: 'science', get label() { return term('icons', 'science', 'Science') }, color: '#2f9c95', glyph: FlaskConical, short: 'Sc' },
  rock: { key: 'rock', get label() { return term('icons', 'rock', 'Rock') }, color: '#8b8b8b', glyph: Mountain, short: 'Ro' },
  water: { key: 'water', get label() { return term('icons', 'water', 'Water') }, color: '#3d86d6', glyph: Droplet, short: 'Wa' },
}

/** The fifteen icons in the order of the player panel grid (3 rows of 5). */
export const ICON_ORDER = [
  'africa', 'americas', 'asia', 'australia', 'europe',
  'bird', 'predator', 'herbivore', 'reptile', 'primate',
  'bear', 'pet', 'science', 'rock', 'water',
] as const

export const CONTINENTS = ['africa', 'americas', 'asia', 'australia', 'europe']

/** Look an icon up by tag, requirement or token name ("HerbivoreTag", "science", "ScienceIcon"). */
export function iconMeta(name: string): IconMeta | undefined {
  const k = name.toLowerCase().replace(/(tag|icon)$/, '')
  if (k === 'seaanimal') return ICON_META.water
  return ICON_META[k]
}

/** Plain-text version of engine markup such as "{Appeal-3}" or "{XToken}". */
export function cleanText(s: string): string {
  return s
    .replace(/\*\*/g, '')
    .replace(/\{ConservationPoint(?:-(\w+))?\}/g, (_, v?: string) => (v ? `${v} conservation` : 'conservation'))
    .replace(/\{XToken\}/g, 'X')
    .replace(/\{([A-Za-z]+)(?:-([^}]+))?\}/g, (_, name: string, v?: string) => `${v ? v + ' ' : ''}${name.toLowerCase()}`)
}

/**
 * Appeal value the conservation marker points at. Same formula as `tables.target_appeal`:
 * the markers cross when appeal reaches it.
 */
export function targetAppeal(conservation: number): number {
  const c = Math.max(0, conservation)
  const label = c <= 10 ? 2 * c - 14 : 6 + 3 * (c - 10)
  return 100 - label
}

/** Appeal still required to cross, at conservation 0. Every game starts this far from the end. */
const OPENING_GAP = targetAppeal(0)

export interface RaceProgress {
  /** 0 at the opening position, 100 once the leader's markers have crossed. */
  percent: number
  leader: number
  appeal: number
  conservation: number
  /** Appeal the leader still needs. 0 once the markers have crossed. */
  remaining: number
  tied: boolean
}

/**
 * How far the game has gone, from the leading player's appeal and conservation.
 * Score is appeal minus the appeal value conservation points at; the leader is whoever
 * has closed more of the opening 114-point gap.
 */
export function raceProgress(players: Pick<Player, 'idx' | 'appeal' | 'conservation'>[]): RaceProgress {
  const scored = players.map((p) => ({ ...p, score: p.appeal - targetAppeal(p.conservation) }))
  const leader = scored.reduce((best, p) => (p.score > best.score ? p : best))
  const remaining = Math.max(0, -leader.score)
  const percent = Math.min(100, Math.max(0, Math.round(((OPENING_GAP - remaining) / OPENING_GAP) * 100)))
  const tied = scored.filter((p) => p.score === leader.score).length > 1
  return { percent, leader: leader.idx, appeal: leader.appeal, conservation: leader.conservation, remaining, tied }
}

export function pct(p: number | undefined): string {
  if (p === undefined) return ''
  if (p > 0 && p < 0.001) return '<0.1%'
  return `${(p * 100).toFixed(p < 0.1 ? 1 : 0)}%`
}

/** Every card the board mentions, by id. */
export function cardIndex(board: Board): Map<string, Card> {
  const m = new Map<string, Card>()
  const add = (c: Card | null | undefined) => {
    if (c) m.set(c.id, c)
  }
  for (const p of board.players) {
    p.hand?.forEach(add)
    p.final_cards?.forEach(add)
    p.known_hand?.forEach(add)
    p.zoo_cards.forEach(add)
  }
  board.display.forEach((d) => add(d.card))
  board.projects.forEach((p) => add(p.card))
  board.decision?.cards?.forEach((c) => { if (!m.has(c.id)) add(c) })
  return m
}

export function humanPlayer(board: Board): Player {
  return board.players.find((p) => p.you) ?? board.players[board.human]
}

export function aiPlayer(board: Board): Player {
  return board.players.find((p) => !p.you) ?? board.players[1 - board.human]
}

export interface PlaceGroup {
  id: string
  building: string
  size: number
  cost: number | null
  options: Option[]
}

export function placeGroups(options: Option[]): PlaceGroup[] {
  const groups = new Map<string, PlaceGroup>()
  for (const o of options) {
    if (o.type !== 'place' || !o.cells || !o.building) continue
    const id = `${o.building}:${o.size ?? 0}`
    const cost = /for (\d+)/.exec(o.label)?.[1]
    const g = groups.get(id) ?? { id, building: o.building, size: o.size ?? o.cells.length, cost: cost ? Number(cost) : null, options: [] }
    g.options.push(o)
    groups.set(id, g)
  }
  return [...groups.values()]
}

export const cellKey = (q: number, r: number) => `${q},${r}`

export const ACTION_HEX: Record<ActionName, string> = {
  animals: '#059669',
  build: '#d97706',
  cards: '#0284c7',
  association: '#7c3aed',
  sponsors: '#e11d48',
}


/** Printed card colours by type: background and name banner. */
export const CARD_TYPE_STYLE: Record<string, { bg: string; banner: string; label: string }> = {
  animal: { bg: '#fbf3e2', banner: '#ef8f1c', get label() { return term('cardTypes', 'animal', 'Animal') } },
  sponsor: { bg: '#e8f0f8', banner: '#2a68b0', get label() { return term('cardTypes', 'sponsor', 'Sponsor') } },
  project: { bg: '#e6f2e1', banner: '#2f6b3a', get label() { return term('cardTypes', 'project', 'Project') } },
  endgame: { bg: '#f6e6df', banner: '#a5543a', get label() { return term('cardTypes', 'endgame', 'Final scoring') } },
}
