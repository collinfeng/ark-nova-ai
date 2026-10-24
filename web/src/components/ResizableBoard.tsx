import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

const CENTER_MIN = 320
/** Below this board width the three columns stack into one. */
const NARROW = 900
const SPACING = 48 // Two 12px gaps and 12px padding on both sides.

interface Column {
  key: string
  fallback: number
  min: number
  max: number
}
const RIGHT: Column = { key: 'ark.rightPanelWidth', fallback: 340, min: 280, max: 680 }
const LEFT: Column = { key: 'ark.leftPanelWidth', fallback: 300, min: 240, max: 520 }

function load(col: Column) {
  try {
    const saved = localStorage.getItem(col.key)
    const width = saved === null ? col.fallback : Number(saved)
    return Number.isFinite(width) ? Math.max(col.min, Math.min(col.max, width)) : col.fallback
  } catch {
    return col.fallback
  }
}

/** A column width the user can drag. `limit` is the most the window leaves room for. */
function useColumn(col: Column, limit: number) {
  const [preferred, setPreferred] = useState(() => load(col))
  const max = Math.max(col.min, Math.min(col.max, limit)) // the saved preference returns when the window widens
  const clamp = (value: number) => Math.round(Math.max(col.min, Math.min(max, value)))
  const width = clamp(preferred)
  const latest = useRef(width)
  const update = (value: number, persist = false) => {
    const next = clamp(value)
    latest.current = next
    setPreferred(next)
    if (persist) {
      try {
        localStorage.setItem(col.key, String(next))
      } catch {
        // Still usable when browser storage is unavailable.
      }
    }
  }
  return { col, width, max, latest, update }
}

type ColumnState = ReturnType<typeof useColumn>

/** The draggable separator on one side of the map column. Dragging towards the map narrows the column. */
function Separator({ side, column, onDragging }: { side: 'left' | 'right'; column: ColumnState; onDragging: (on: boolean) => void }) {
  const { col, width, max, latest, update } = column
  const drag = useRef<{ x: number; width: number; pointerId: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const sign = side === 'right' ? -1 : 1 // the right column grows when the pointer moves left
  const set = (on: boolean) => {
    setDragging(on)
    onDragging(on)
  }
  const finish = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId !== event.pointerId) return
    drag.current = null
    set(false)
    update(latest.current, true)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 40 : 16
    let next: number
    switch (event.key) {
      case 'ArrowLeft': next = width - sign * step; break
      case 'ArrowRight': next = width + sign * step; break
      case 'Home': next = col.min; break
      case 'End': next = max; break
      default: return
    }
    event.preventDefault()
    update(next, true)
  }
  const label = side === 'right' ? t('accessibility.resizeRightPanel', 'Resize right panel') : t('accessibility.resizeLeftPanel', 'Resize left panel')
  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label={label}
      aria-controls={side === 'right' ? 'right-panel' : undefined}
      aria-valuemin={col.min}
      aria-valuemax={max}
      aria-valuenow={width}
      aria-valuetext={`${width}px`}
      title={t('accessibility.resizeRightPanelHint', 'Drag to resize; double-click to reset. Use Left/Right arrows, or Shift for larger steps.')}
      className={cn('group absolute top-3 bottom-3 z-20 flex w-3 touch-none cursor-col-resize items-center justify-center rounded focus-visible:bg-sky-100 focus-visible:outline-2 focus-visible:outline-sky-500', dragging && 'bg-sky-100')}
      style={{ [side]: width + 12 }}
      onPointerDown={(event) => {
        if (!event.isPrimary || event.button !== 0) return
        event.preventDefault()
        event.currentTarget.focus()
        event.currentTarget.setPointerCapture(event.pointerId)
        drag.current = { x: event.clientX, width, pointerId: event.pointerId }
        latest.current = width
        set(true)
      }}
      onPointerMove={(event) => {
        if (drag.current?.pointerId !== event.pointerId) return
        update(drag.current.width + sign * (event.clientX - drag.current.x))
      }}
      onPointerUp={finish}
      onPointerCancel={finish}
      onLostPointerCapture={finish}
      onDoubleClick={() => update(col.fallback, true)}
      onKeyDown={onKeyDown}
    >
      <span aria-hidden="true" className={cn('h-12 w-1 rounded-full bg-slate-300 transition-colors group-hover:bg-sky-500 group-focus-visible:bg-sky-500', dragging && 'bg-sky-500')} />
    </div>
  )
}

/** The three board columns, with a draggable separator on each side of the map column. */
export function ResizableBoard({ children, className }: { children: ReactNode; className?: string }) {
  const container = useRef<HTMLElement>(null)
  const [containerWidth, setContainerWidth] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    const element = container.current
    if (!element) return
    const observer = new ResizeObserver(() => setContainerWidth(element.clientWidth))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Each side may grow until the map column is down to CENTER_MIN, given the other side's width.
  const room = containerWidth === null ? Infinity : containerWidth - CENTER_MIN - SPACING
  const left = useColumn(LEFT, room - RIGHT.min)
  const right = useColumn(RIGHT, room - left.width)

  // Narrow screens (phones): one column that scrolls as a whole; the columns' order comes from their classes.
  const narrow = containerWidth !== null && containerWidth < NARROW
  return (
    <main
      ref={container}
      className={cn('relative grid min-h-0 flex-1 gap-3 p-3 transition-opacity', narrow && 'overflow-y-auto p-2', dragging && 'cursor-col-resize select-none', className)}
      style={narrow ? { gridTemplateColumns: 'minmax(0,1fr)', gridAutoRows: 'max-content', alignContent: 'start' } : { gridTemplateColumns: `${left.width}px minmax(0,1fr) ${right.width}px` }}
      data-narrow={narrow || undefined}
    >
      {children}
      {!narrow && <Separator side="left" column={left} onDragging={setDragging} />}
      {!narrow && <Separator side="right" column={right} onDragging={setDragging} />}
    </main>
  )
}
