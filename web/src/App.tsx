import { aiName, networkLabel } from '@/lib/networks'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, ArrowDown, ArrowUp, Maximize2, Minimize2, X } from 'lucide-react'
import { api, getToken, QueueError, SIGNED_OUT, signOut } from '@/api/client'
import type { Board, NewGameParams, Option } from '@/api/types'
import { aiPlayer, cardIndex, humanPlayer, placeGroups } from '@/lib/game'
import { t } from '@/i18n'
import { useSettings } from '@/lib/settings'
import { cn } from '@/lib/utils'
import { ActivityTabs } from '@/components/ActivityTabs'
import { DecisionPanel } from '@/components/DecisionPanel'
import { TurnFeed } from '@/components/Feed'
import { LoginPage } from '@/components/LoginPage'
import { QueuePage } from '@/components/QueuePage'
import { GameOverDialog } from '@/components/GameOverDialog'
import { HandRow } from '@/components/HandRow'
import { PlayerPanel } from '@/components/PlayerPanel'
import { ZooCards } from '@/components/ZooCards'
import { DisplayPanel } from '@/components/DisplayPanel'
import { ProjectsPanel } from '@/components/ProjectsPanel'
import { ResizableBoard } from '@/components/ResizableBoard'
import { HexMap } from '@/components/HexMap'
import { AssociationBoard, Tip, TracksPanel, ZooSide } from '@/components/TracksPanel'
import { TitleTips } from '@/components/TitleTips'
import { TurnControls } from '@/components/TurnControls'
import { NewGameDialog } from '@/components/NewGameDialog'
import { TopBar } from '@/components/TopBar'
import { TooltipProvider } from '@/components/ui/tooltip'

type Who = 'you' | 'ai'

export default function App() {
  const [board, setBoard] = useState<Board | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [hintsOn, setHints] = useState(false)
  // Place in the line while the server is full (the account's player limit); null when playing.
  const [queue, setQueue] = useState<number | null>(null)
  const [signedIn, setSignedIn] = useState(() => getToken() !== null)
  // Without a saved login, ask once whether the server signs this browser in itself (a local server may skip the login).
  const [probing, setProbing] = useState(() => getToken() === null)
  useEffect(() => {
    if (!probing) return
    void api.autoSignedIn().then((ok) => {
      if (ok) setSignedIn(true)
      setProbing(false)
    })
  }, [probing])
  // The server decides who may see the AI's hints: an account without them never gets the numbers.
  const canHint = !!board?.can_hint
  const hints = hintsOn && canHint
  const [newOpen, setNewOpen] = useState(false)
  // Right after signing in the New game window comes first, so the opponent is chosen before any game exists.
  const [choosing, setChoosing] = useState(false)
  const started = useRef(false)
  const [who, setWho] = useState<Who>('you')
  const [groupSel, setGroupSel] = useState<{ sig: string; id: string | null }>({ sig: '', id: null })
  const [draft, setDraft] = useState(false)  // a picker holds picks not yet confirmed
  const [pickReset, setPickReset] = useState(0)
  const [dismissedOver, setDismissedOver] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem('ark.expandMap') === '1'
    } catch {
      return false
    }
  })
  const toggleExpanded = () =>
    setExpanded((v) => {
      try {
        localStorage.setItem('ark.expandMap', v ? '0' : '1')
      } catch {
        /* ignore */
      }
      return !v
    })
  const [handedOver, setHandedOver] = useState(false)
  const [banner, setBanner] = useState(false)
  const [ending, setEnding] = useState(false)
  const [hoverOption, setHoverOption] = useState<Option | null>(null)
  // The decision stays in its place under the zoo; when it is scrolled out of sight on your turn, a pill brings it back.
  const centerRef = useRef<HTMLDivElement>(null)
  const decisionRef = useRef<HTMLElement>(null)
  const [decisionSeen, setDecisionSeen] = useState(true)
  const [decisionAbove, setDecisionAbove] = useState(false)
  const hasBoard = !!board
  useEffect(() => {
    const el = decisionRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        setDecisionSeen(entry.isIntersecting)
        setDecisionAbove(entry.boundingClientRect.top < (entry.rootBounds?.top ?? 0))
      },
      { threshold: 0.15 },  // the viewport, clipped by whichever column scrolls (all of them on a phone)
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasBoard, signedIn, queue])

  // A language change fetches the board again: the server writes titles, option labels and card text.
  const { lang } = useSettings()
  const langRef = useRef(lang)
  useEffect(() => {
    if (langRef.current === lang) return
    langRef.current = lang
    if (boardRef.current === null) return
    api.state().then(setBoard, () => undefined)
  }, [lang])

  const boardRef = useRef<Board | null>(null)
  useEffect(() => {
    boardRef.current = board
  }, [board])
  useEffect(() => {
    if (!error) return
    const timer = window.setTimeout(() => setError(null), 4000)
    return () => window.clearTimeout(timer)
  }, [error])
  const busyRef = useRef(true)
  useEffect(() => {
    busyRef.current = busy
  }, [busy])
  useEffect(() => {
    const onFocus = () => {
      if (busyRef.current || boardRef.current === null) return
      api.state().then(setBoard, (e) => e instanceof QueueError && setQueue(e.position))
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [])

  // The hint model is kept per browser: a new game, a reload or another login starts from the saved choice.
  const chooseHintModel = (name: string) => {
    try {
      localStorage.setItem('ark.hintModel', name)
    } catch {
      /* the choice still applies to this game */
    }
    void run(() => api.setHintModel(name))
  }
  const run = useCallback(async (fn: () => Promise<Board>) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      setBoard(await fn())
    } catch (e) {
      if (e instanceof QueueError) {
        setQueue(e.position)
        return
      }
      const msg = e instanceof Error ? e.message : String(e)
      // Always resync: the server may have restarted or moved on.
      try {
        const fresh = await api.state()
        const old = boardRef.current
        const same = old && fresh.seed === old.seed && fresh.phase === old.phase && fresh.decision?.kind === old.decision?.kind
        setBoard(fresh)
        if (same || !old) setError(msg)
      } catch {
        setError(msg)
      }
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    const out = () => {
      setSignedIn(false)
      setBoard(null)
    }
    window.addEventListener(SIGNED_OUT, out)
    return () => window.removeEventListener(SIGNED_OUT, out)
  }, [])

  const askForPlace = useCallback(() => {
    api.state().then(
      (b) => {
        setBoard(b)
        setQueue(null)
      },
      (e) => e instanceof QueueError && setQueue(e.position),
    )
  }, [])
  const waiting = queue !== null && queue > 0
  useEffect(() => {
    // Waiting for a place: ask again every few seconds; the server keeps this browser's place in line while we do.
    // With the line full (queue 0) nothing is held, so the page waits for the player to try again.
    if (!waiting) return
    const timer = window.setInterval(askForPlace, 4000)
    return () => window.clearInterval(timer)
  }, [waiting, askForPlace])

  useEffect(() => {
    // Initial load of whatever game this account holds.
    if (!signedIn) started.current = false
    else if (choosing) setBusy(false)  // nothing loads while the New game window is up, so Start must be free
    else if (!started.current) {
      started.current = true
      void run(api.state)
    }
  }, [run, signedIn, choosing])

  // Apply the saved hint model to a game that does not use it yet (once per game).
  const hintApplied = useRef<number | null>(null)
  useEffect(() => {
    if (!board || !board.can_hint || hintApplied.current === board.seed) return
    let wanted: string | null = null
    try {
      wanted = localStorage.getItem('ark.hintModel')
    } catch {
      /* none saved */
    }
    hintApplied.current = board.seed
    // Off Map 0 the saved model may know Map 0 only: those games start with the opponent's own hints.
    if (wanted && wanted !== board.hint_model && board.map === 'map0') void run(() => api.setHintModel(wanted))
  }, [board, run])

  const cardsById = useMemo(() => (board ? cardIndex(board) : new Map()), [board])
  const decision = board?.decision ?? null
  const groups = useMemo(() => placeGroups(decision?.options ?? []), [decision])
  const sig = board ? `${board.seed}:${board.records.length}:${decision?.kind ?? ''}` : ''
  const selectedId = groupSel.sig === sig ? groupSel.id : null  // always offered, even with a single building type
  const group = groups.find((g) => g.id === selectedId) ?? null
  // The same decision can come back after an undo: it starts again at the building choice, not at the old placement.
  useEffect(() => setGroupSel({ sig: '', id: null }), [sig])

  const move = (index: number) => {
    setHandedOver(false)
    void run(() => api.move(index))
  }
  /** Several choices of one decision in a row (take 3 cards, discard 2): each is found by its key, since
   *  the option indexes change after every move. Stops when the decision has moved on. */
  const moveMany = (keys: string[][]) => {
    setHandedOver(false)
    void run(async () => {
      let b = boardRef.current!
      for (const key of keys) {
        const o = b.decision?.options.find((x) => JSON.stringify(x.key) === JSON.stringify(key))
        if (!o) break
        b = await api.move(o.index)
      }
      return b
    })
  }
  const endTurn = useCallback(() => {
    setEnding(true)
    void run(async () => {
      try {
        const b = await api.endTurn()
        setHandedOver(true)
        setBanner(true)
        return b
      } finally {
        setEnding(false)
      }
    })
  }, [run])
  useEffect(() => {
    if (!banner) return
    const timer = window.setTimeout(() => setBanner(false), 1800)
    return () => window.clearTimeout(timer)
  }, [banner])
  const endPhase = board?.phase === 'end_turn' && !busy
  useEffect(() => {
    if (!endPhase) return
    const h = (e: KeyboardEvent) => {
      const target = e.target instanceof Element ? e.target : null
      if (e.key !== 'Enter' || e.repeat || target?.closest('input,textarea,select,[role=dialog]')) return
      e.preventDefault()
      endTurn()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [endPhase, endTurn])
  const turnPill: 'you' | 'ai' | 'over' | null = !board ? null : board.over || board.phase === 'over' ? 'over' : ending ? 'ai' : 'you'
  // Undo first drops what is picked on the page but not confirmed (ticked cards, X-tokens, the building
  // chosen for placing); only then does it take back a move on the server.
  const picking = draft || selectedId !== null
  const undo = () => {
    if (picking) {
      setGroupSel({ sig: '', id: null })
      setPickReset((n) => n + 1)
      return
    }
    void run(api.undo)
  }
  const redo = () => {
    void run(api.redo)
  }
  const restartTurn = () => {
    void run(api.restartTurn)
  }
  const startNew = (params: NewGameParams) => {
    setNewOpen(false)
    started.current = true
    setChoosing(false)
    setDismissedOver(null)
    setWho('you')
    void run(() => api.newGame(params))
  }
  // Quit deletes the game, frees the place and signs out: back to the login page.
  const quit = () => {
    setBusy(true)
    void api
      .quit()
      .catch(() => undefined)
      .finally(() => {
        setWho('you')
        setBusy(false)
        signOut()
      })
  }
  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.save()
      setNotice(t('app.savedTo', 'Saved to {path}', { path: r.path }))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (!signedIn) {
    if (probing) return null
    return <LoginPage onSignedIn={() => (setChoosing(true), setNewOpen(true), setSignedIn(true))} />
  }

  if (queue !== null) {
    return <QueuePage position={queue} onRetry={askForPlace} onSignOut={() => signOut()} />
  }

  const me = board ? humanPlayer(board) : null
  const ai = board ? aiPlayer(board) : null
  const placing = !!group
  const mapBig = expanded || placing
  const shown = placing ? 'you' : who
  const shownPlayer = shown === 'you' ? me : ai

  let highlight: number | null = null
  if (hoverOption && hoverOption.key[0] === 'play' && typeof hoverOption.key[2] === 'number') highlight = hoverOption.key[2]

  const myTurn = !!board && !!me && board.phase === 'your_decision' && board.decision?.player === me.idx
  const overKey = board ? `${board.seed}:${board.records.length}` : ''
  const overOpen = !!board?.over && dismissedOver !== overKey

  return (
    <TooltipProvider delay={150}>
      <div className="flex h-screen min-h-[640px] flex-col overflow-hidden bg-slate-50 text-slate-900">
        <TopBar
          board={board}
          busy={busy}
          turn={turnPill}
          hints={hints}
          canHint={canHint}
          user={board?.user}
          onHints={setHints}
          onHintModel={chooseHintModel}
          onQuit={quit}
          onSignOut={() => signOut()}
          onNewGame={() => setNewOpen(true)}
          onSave={() => void save()}
        />
        {banner && (
          <div className="pointer-events-none fixed top-14 left-1/2 z-50 -translate-x-1/2 animate-in rounded-full bg-sky-600 px-8 py-3 text-xl font-bold text-white shadow-xl fade-in zoom-in-95">
            Your turn
          </div>
        )}
        {(error || notice) && (
          <div
            role="alert"
            className={cn(
              'mx-4 mt-2 flex shrink-0 items-center gap-2 rounded-lg border px-3 py-1.5 text-sm',
              error ? 'border-red-200 bg-red-50 text-red-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800',
            )}
          >
            {error && <AlertCircle className="size-4" />}
            <span className="flex-1">{error ?? notice}</span>
            <button type="button" onClick={() => (setError(null), setNotice(null))} aria-label={t('common.dismiss', 'Dismiss')}>
              <X className="size-4" />
            </button>
          </div>
        )}

        {!board || !me || !ai ? (
          <div className="p-10 text-center text-sm text-muted-foreground">{busy ? t('app.loadingGame', 'Loading game...') : t('app.noGameLoaded', 'No game loaded.')}</div>
        ) : (
          <ResizableBoard className={busy ? 'opacity-80' : undefined}>
            <aside className="scroll-area flex min-h-0 flex-col gap-2 overflow-y-auto in-data-narrow:order-2 in-data-narrow:grid in-data-narrow:grid-cols-[repeat(auto-fill,minmax(300px,1fr))] in-data-narrow:items-start in-data-narrow:overflow-visible">
              <PlayerPanel p={me} board={board} name="you" active={board.decision?.kind === 'turn' && board.decision.player === me.idx} />
              <PlayerPanel p={ai} board={board} name={networkLabel(board.ai_name)} active={false} />
              <div className="flex min-h-0 flex-col in-data-narrow:col-span-full in-data-narrow:max-h-[80vh] in-data-narrow:overflow-y-auto">
                <ActivityTabs board={board} handedOver={handedOver} canHint={canHint} />
              </div>
            </aside>
            <div ref={centerRef} className="scroll-area relative flex min-h-0 min-w-0 flex-col gap-2 overflow-y-auto in-data-narrow:order-1 in-data-narrow:overflow-visible">
              <div className="shrink-0">
                <DisplayPanel board={board} />
              </div>
              <section className="flex shrink-0 flex-col rounded-xl border bg-white px-2 py-1.5 shadow-xs">
                <div className="mb-1 flex shrink-0 items-center justify-between gap-2">
                  <div className="inline-flex rounded-lg bg-muted p-0.5 text-sm" role="tablist" aria-label={t('map.zooSelector', 'Whose zoo')}>
                    {(['you', 'ai'] as const).map((w) => (
                      <button
                        key={w}
                        type="button"
                        role="tab"
                        aria-selected={shown === w}
                        disabled={placing && w === 'ai'}
                        onClick={() => setWho(w)}
                        className={cn(
                          'rounded-md px-3 py-0.5 font-medium transition disabled:opacity-40',
                          shown === w ? (w === 'you' ? 'bg-white text-sky-800 shadow-sm' : 'bg-white text-orange-800 shadow-sm') : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {w === 'you' ? t('map.yourZoo', 'Your zoo') : t('map.aiZoo', "{name}'s zoo", { name: aiName() })}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap justify-end gap-x-3 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1"><i className="size-2.5 rounded-sm" style={{ background: '#f1e6c6' }} />{t('map.plain', 'plain')}</span>
                    <span className="flex items-center gap-1"><i className="size-2.5 rounded-sm" style={{ background: '#bddaf0' }} />{t('map.water', 'water')}</span>
                    <span className="flex items-center gap-1"><i className="size-2.5 rounded-sm" style={{ background: '#c9c8c4' }} />{t('map.rock', 'rock')}</span>
                    <span className="flex items-center gap-1"><i className="size-2.5 rounded-sm border border-[#b42318]" style={{ background: '#f1c3bb' }} />{t('map.buildTwoOnly', 'red II: Build II only')}</span>
                  </div>
                  <button
                    type="button"
                    onClick={toggleExpanded}
                    disabled={placing}
                    title={mapBig ? t('map.smallerMap', 'Smaller map') : t('map.biggerMap', 'Bigger map')}
                    aria-label={mapBig ? t('map.smallerMap', 'Smaller map') : t('map.biggerMap', 'Bigger map')}
                    className={cn('rounded-md border p-1 hover:bg-muted disabled:opacity-60', mapBig && 'bg-sky-100')}
                  >
                    {mapBig ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
                  </button>
                </div>
                <div className="@container">
                  <div className="flex flex-col gap-2 @xl:flex-row">
                    <div className={cn('min-h-0 min-w-0 flex-1', mapBig ? 'h-[max(560px,72vh)]' : 'h-[clamp(360px,52vh,600px)]')}>
                      {shownPlayer && (
                        <HexMap
                          key={shown}
                          zoo={shownPlayer.zoo}
                          cardsById={cardsById}
                          highlightBuilding={highlight !== null && shown === 'you' ? highlight : null}
                          placement={group && shown === 'you' ? { options: group.options, hints, disabled: busy, onPick: move } : undefined}
                        />
                      )}
                    </div>
                    {shownPlayer && <div className="@xl:w-52 @xl:shrink-0"><ZooSide board={board} player={shownPlayer} /></div>}
                  </div>
                </div>
                {shownPlayer && (
                  <div className="mt-2 border-t pt-2">
                    <div>
                      <ZooCards p={shownPlayer} title={shown === 'you' ? t('played.yourCards', 'Your played cards') : t('played.aiCards', "{name}'s played cards", { name: aiName() })} />
                    </div>
                  </div>
                )}
              </section>
              {board.decision?.kind === 'setup_keep' && (
                <div className="shrink-0">
                  <HandRow me={me} finalOnly />
                </div>
              )}
              <section
                ref={decisionRef}
                className={cn('flex shrink-0 scroll-mt-2 flex-col overflow-hidden rounded-xl border bg-white shadow-xs', board.phase === 'end_turn' && 'border-sky-400')}
              >
                <TurnControls board={board} busy={busy || ending} picking={picking} onUndo={undo} onRedo={redo} onRestart={restartTurn} onEndTurn={endTurn} />
                {board.decision?.kind !== 'setup_keep' && <TurnFeed lines={board.turn_feed ?? []} />}
                <div className={cn('flex flex-col', ending && 'pointer-events-none opacity-50')}>
                  <DecisionPanel
                    board={board}
                    me={me}
                    cardsById={cardsById}
                    hints={hints}
                    busy={busy}
                    group={group}
                    groups={groups}
                    onGroup={(id) => setGroupSel({ sig, id })}
                    onMove={move}
                    onMoveMany={moveMany}
                    onHoverOption={setHoverOption}
                    reset={pickReset}
                    onDraft={setDraft}
                  />
                </div>
              </section>
              {board.decision?.kind !== 'setup_keep' && (
                <div className="shrink-0">
                  <HandRow me={me} />
                </div>
              )}
              {myTurn && !decisionSeen && (
                <button
                  type="button"
                  onClick={() => decisionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                  className="sticky bottom-3 z-30 mx-auto flex shrink-0 items-center gap-1 rounded-full bg-sky-600 px-4 py-1.5 text-sm font-semibold text-white shadow-lg hover:bg-sky-700"
                >
                  {t('app.yourTurnJump', 'Your turn')} {decisionAbove ? <ArrowUp className="size-4" /> : <ArrowDown className="size-4" />}
                </button>
              )}
            </div>
            <aside id="right-panel" className="scroll-area flex min-h-0 min-w-0 flex-col gap-2 overflow-y-auto in-data-narrow:order-3 in-data-narrow:overflow-visible">
              <div className="shrink-0">
                <TracksPanel board={board} />
              </div>
              <div className="shrink-0">
                <AssociationBoard board={board} />
              </div>
              <section className="shrink-0 rounded-xl border bg-white shadow-xs" aria-label={t('tabs.projects', 'Projects')}>
                <Tip side="left" tip={t('projects.titleTip', 'Conservation projects: support one with the Association action at strength 5. Each slot needs icons in your zoo (or releases an animal) and gives conservation, and you take one of your map tokens. Base projects stay; at most {n} played ones stay above the board, a new one pushes the oldest out.', { n: 2 })} className="block cursor-help px-3 pt-2 text-sm font-semibold">{t('tabs.projects', 'Projects')}</Tip>
                <ProjectsPanel projects={board.projects} humanIdx={me.idx} />
              </section>
            </aside>
          </ResizableBoard>
        )}

        <TitleTips />
        <NewGameDialog
          open={newOpen}
          onOpenChange={(o) => (setNewOpen(o), !o && setChoosing(false))}
          onStart={startNew}
          busy={busy}
          first={choosing}
          onSignOut={() => signOut()}
        />
        {board?.over && (
          <GameOverDialog
            board={board}
            open={overOpen}
            onClose={() => setDismissedOver(overKey)}
            onNewGame={() => (setDismissedOver(overKey), setNewOpen(true))}
          />
        )}
      </div>
    </TooltipProvider>
  )
}
