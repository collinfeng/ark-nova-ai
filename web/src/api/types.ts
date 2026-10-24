export type CardType = 'animal' | 'sponsor' | 'project' | 'endgame'

export interface SizeLimit {
  min?: number
  max?: number
}

export interface Reward {
  reward: string
  amount: number
}

export interface ProjectSlot {
  position: number
  required: number | null
  rewards: Reward[]
  /** Release projects: allowed animal sizes. */
  size?: SizeLimit | number | null
}

export interface CardEffect {
  timing: 'passive' | 'immediate' | 'income' | 'endgame' | string
  text: string
  icon_only: boolean
}

export interface CardAbility {
  name: string
  keyword: string
  value: number | string | null
  text: string
}

export interface Enclosure {
  size: number | null
  rock: number
  water: number
  special: { type: string; size: number }[]
}

export interface CardStatus {
  ready: boolean
  why: string
  cost: number
  /** Keys of the play conditions not met (icon names, "reputation", "animalsII", ...). */
  unmet?: string[]
}

export interface Card {
  id: string
  name: string
  type: CardType
  tags: string[]
  requirements: string[]
  appeal: number
  conservation: number
  reputation: number
  text: string[]
  effects: CardEffect[]
  abilities: CardAbility[]
  min_reputation?: number
  max_appeal?: number
  /** Present on your hand and the display; null for projects and final scoring cards. */
  status?: CardStatus | null
  // animals
  cost?: number
  size?: number
  latin?: string
  enclosure?: Enclosure
  // sponsors
  level?: number
  human?: boolean
  // projects
  icon?: string
  category?: string
  slots?: ProjectSlot[]
  // final scoring
  scoring?: { threshold: number; conservation: number }[]
}

export type ActionName = 'animals' | 'build' | 'cards' | 'association' | 'sponsors'

export interface Slot {
  action: ActionName
  strength: number
  upgraded: boolean
  /** Tokens on the card: 'multiplier' (x2), 'venom', 'constriction'. */
  tokens: string[]
  playable?: boolean
  reason?: string
}

export type Terrain = 'plain' | 'water' | 'rock'

export interface Cell {
  q: number
  r: number
  x: number
  y: number
  terrain: Terrain
  bonus: string | null
  build2: boolean
  building: number | null
  /** A special site of the map on this space (see lib/maps.ts), if any. */
  site?: string | null
}

export type BuildingKind = 'enclosure' | 'kiosk' | 'pavilion' | 'petting_zoo' | 'reptile_house' | 'aviary' | 'unique'

export interface Building {
  id: number
  kind: BuildingKind | string
  size: number
  capacity: number
  occupied: boolean
  used: number
  /** For unique buildings this is a card id. */
  name: string | null
  cells: [number, number][]
  animals: string[]
  animal_cards?: Card[]
  sponsor_card?: Card | null
}

export interface Zoo {
  cells: Cell[]
  buildings: Building[]
}

export interface Player {
  idx: number
  you: boolean
  appeal: number
  conservation: number
  reputation: number
  money: number
  income: number
  xtokens: number
  workers: number
  active_workers: number
  points: number
  folders: number
  hand_limit: number
  slots: Slot[]
  icons: Record<string, number>
  partner_zoos: string[]
  universities: string[]
  projects_supported: number
  zoo_cards: Card[]
  zoo: Zoo
  hand_size: number
  last_action: string | null
  hand?: Card[]
  final_cards?: Card[]
  known_hand?: Card[]
}

export interface DisplaySlot {
  folder: number
  card: Card | null
  in_reach: boolean
  /** The reputation that brings this folder into reach. */
  reach_reputation?: number
  status?: CardStatus | null
}

export interface Project {
  card: Card
  /** slot position -> player index, or "blocked" */
  tokens: Record<string, number | 'blocked'>
  base: boolean
}

export interface Option {
  index: number
  label: string
  key: (string | number)[]
  cards: string[]
  type: string
  action?: ActionName
  x?: number
  cells?: [number, number][]
  building?: string
  size?: number
  ai_prob?: number
  /** A placement: what it brings (covered bonus spaces, the building's own effect, kiosk income, map sites). */
  gains?: PlaceGain[]
  /** What the choice does, when the label alone does not say (upgrades, partner zoos, universities, animal homes). */
  detail?: string
}

export interface PlaceGain {
  k: string
  n: number
}

export interface Decision {
  player: number
  kind: string
  title: string
  options: Option[]
  /** The cards the options name, in full, even when they are not on the board yet (a drawn pick) */
  cards?: Card[]
  /** Hunter: every revealed card, including non-animals that cannot be selected. */
  revealed_cards?: Card[]
  /** A rule policy hint (`rule`) puts 100% on its move and has no win chance. */
  ai?: { best: number; value?: number; win_chance?: number; rule?: boolean }
  keep_from?: string[]
  keep_count?: number
  /** take_card only: how many cards this player still has to take, this one included */
  remaining?: number
  /** Take or discard several cards at once: how many the decision needs in all */
  pick?: { count: number }
  /** A line of explanation under the title (the rule of this decision), in the board's language */
  note?: string
}

/** One thing a move changed (or an event), with the reason, as the server words it. */
export type FeedLine =
  | { who: 'you' | 'ai'; kind: string; amount: number; text: string; why: string | null }
  | { note: 'break' | 'info'; text: string; why?: string | null }

export interface AiMove {
  /** What this move gained and spent, and why. */
  feed?: FeedLine[]
  kind: string
  label: string
  /** Cards the label names (shown as chips that pop up the card) */
  cards?: Card[]
  /** The decision the move answered, in the board's language. */
  title?: string
  /** Null for moves rebuilt from a save, whose odds were not kept. */
  prob: number | null
}

export interface AiTurnHistory {
  turn: number
  moves: AiMove[]
}

export interface ActivityTurn extends AiTurnHistory {
  actor: 'you' | 'ai'
}

export interface MoveRecord {
  move: number
  kind: string
  chose: string
  /** The hint model that judged this move: a network (file name without .pt) or a rule policy */
  hint?: string
  /** A rule policy puts all its weight (100%) on its move, so any other move has 0% and rank 2 */
  prob: number
  rank: number
  options: number
  ai_best: string
  ai_best_prob: number
  /** null for a rule policy, which has no win estimate */
  value: number | null
  top: { label: string; prob: number }[]
  rule?: boolean
}

export interface TrackEffect {
  kind: string
  amount: number
  label: string
}

export interface ConservationStop {
  at: number
  kind: string
  label: string
  tiles?: { id: string; effects: TrackEffect[] }[]
  choices?: { id: string; effects: TrackEffect[]; available: boolean; claimed_by?: number[] }[]
  money_claimed_by?: number[]
  money?: number
  spent?: boolean
}

export interface ReputationStop {
  at: number
  kind: string
  label: string
}

export interface MapSlot {
  slot: number
  label: string
  effects: TrackEffect[]
}

export interface UniversityChoice {
  id: string
  name: string
  grant: string
}

export interface EdgeToken {
  index: number
  repeats: boolean
  label: string
  effects: TrackEffect[]
}

export interface TrackPlayer {
  idx: number
  conservation: number
  reputation: number
  cards_ii: boolean
  association_ii: boolean
  partner_zoos: number
  universities: number
  workers: number
  /** True while that left-edge token is still on the map. */
  on_map: boolean[]
}

export interface Tracks {
  conservation: { max: number; stops: ConservationStop[] }
  reputation: { max: number; gate: number; stops: ReputationStop[] }
  partner_zoos: { max: number; slots: MapSlot[]; available: string[]; association_from: number; discount: number }
  universities: { max: number; slots: MapSlot[]; available: UniversityChoice[] }
  workers: { max: number; last: TrackEffect[] }
  tokens: EdgeToken[]
  players: TrackPlayer[]
  association?: Association
}

export type TaskName = 'reputation' | 'partner_zoo' | 'university' | 'project'

/** The association board: tasks, every partner zoo and university with its owners, donations, workers per task. */
export interface Association {
  tasks: { task: TaskName; strength: number }[]
  partner_zoos: { id: string; owners: number[]; available: boolean }[]
  universities: { id: string; name: string; grant: string; owners: number[]; available: boolean }[]
  donations: { costs: number[]; final: number; made: number; next: number }
  /** Per player: workers out on each task since the break, and what the next use takes (null: blocked or no free worker). */
  players: { idx: number; out: Record<TaskName, number>; next: Record<TaskName, number | null>; active: number }[]
}

export interface Board {
  seed: number
  map: string
  human: number
  ai_name: string
  over: boolean
  scores: number[] | null
  winners: number[] | null
  break: { pos: number; max: number }
  deck: number
  discard?: number
  display: DisplaySlot[]
  projects: Project[]
  tracks: Tracks
  players: Player[]
  decision: Decision | null
  phase?: 'your_decision' | 'end_turn' | 'over'
  ai_moves: AiMove[]
  ai_history: AiTurnHistory[]
  activity_history?: ActivityTurn[]
  /** Everything your moves this turn changed, with the reasons. */
  turn_feed?: FeedLine[]
  /** The account playing, and whether it may see the AI's hints and win chances */
  user?: string
  can_hint?: boolean
  /** Who gives the hints: "default" (the opponent's own network), a rule policy or a network file */
  hint_model?: string
  /** False for an account that may not save games: the Save button is hidden. */
  can_save?: boolean
  records: MoveRecord[]
  can_undo: boolean
  can_redo: boolean
  /** Some decision of the current turn can be taken back. */
  can_restart_turn: boolean
  /** The next undo goes back into your previous turn, taking back the AI's turn too. */
  undo_leaves_turn: boolean
  /** What you have played this turn, forced moves included. */
  turn_log: string[]
  log: string[]
}

export interface Checkpoints {
  checkpoints: string[]
  default: string
  remote: string | null
  /** The maps a game can be on, Map 0 first. */
  maps?: string[]
  /** The opponents that play every map; the others play Map 0 only. */
  any_map?: string[]
  /** The network the server uses off Map 0 when no opponent is named. */
  map_default?: string | null
}

export interface NewGameParams {
  seed?: number
  human?: 0 | 1
  checkpoint?: string
  map?: string
}
