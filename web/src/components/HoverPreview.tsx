import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { useSettings } from '@/lib/settings'

interface Props {
  /** The enlarged content. */
  preview: React.ReactNode
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
  /** Milliseconds before the preview opens. */
  delay?: number
  as?: 'div' | 'span'
  triggerProps?: React.HTMLAttributes<HTMLElement>
}

/**
 * Hover preview that opens after a short delay. It stays open while the pointer is on the card or
 * on the preview itself (a short grace period lets the pointer cross the gap), and closes when the
 * pointer leaves both, or on a click or a scroll elsewhere. A macOS hard press (Look Up) on the preview's
 * text takes focus from the page and may report the pointer as gone; the preview then waits until the
 * page has focus again and closes only if the pointer is not over it.
 * With "Keep preview open" off (Settings), the preview closes as soon as the pointer leaves the card
 * and lets the pointer pass through it.
 */
export function HoverPreview({ preview, children, className, style, delay = 300, as = 'div', triggerProps }: Props) {
  const { keepPreview } = useSettings()
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const ref = useRef<HTMLElement>(null)
  const pop = useRef<HTMLDivElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const leaving = useRef<number | undefined>(undefined)

  const close = useCallback(() => {
    window.clearTimeout(timer.current)
    window.clearTimeout(leaving.current)
    setOpen(false)
    setPos(null)
  }, [])
  const schedule = () => {
    window.clearTimeout(leaving.current)
    if (open) return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpen(true), delay)
  }
  const stay = () => window.clearTimeout(leaving.current)
  const hovered = () => !!(pop.current?.matches(':hover') || ref.current?.matches(':hover'))
  const leave = () => {
    window.clearTimeout(timer.current)
    window.clearTimeout(leaving.current)
    leaving.current = window.setTimeout(() => {
      if (document.hasFocus()) close()  // otherwise Look Up is showing: decide when focus comes back
    }, 200)
  }

  useEffect(
    () => () => {
      window.clearTimeout(timer.current)
      window.clearTimeout(leaving.current)
    },
    [],
  )
  useEffect(() => {
    if (!open) return
    const off = (e: Event) => {
      if (e.target instanceof Node && pop.current?.contains(e.target)) return  // scrolling or clicking inside the preview
      close()
    }
    const back = () => {
      if (!hovered()) close()
    }
    window.addEventListener('scroll', off, true)
    window.addEventListener('focus', back)
    window.addEventListener('pointerdown', off, true)
    return () => {
      window.removeEventListener('scroll', off, true)
      window.removeEventListener('focus', back)
      window.removeEventListener('pointerdown', off, true)
    }
  }, [open, close])

  useLayoutEffect(() => {
    if (!open || !ref.current || !pop.current) return
    const t = ref.current.getBoundingClientRect()
    const p = pop.current.getBoundingClientRect()
    const gap = 8
    let top = t.top - p.height - gap
    if (top < 8) top = t.bottom + gap
    if (top + p.height > window.innerHeight - 8) top = Math.max(8, window.innerHeight - p.height - 8)
    let left = t.left + t.width / 2 - p.width / 2
    left = Math.min(Math.max(8, left), window.innerWidth - p.width - 8)
    setPos({ left, top })
  }, [open])

  const Tag = as as 'div'
  return (
    <>
      <Tag
        ref={ref as React.RefObject<HTMLDivElement>}
        className={className}
        style={style}
        {...triggerProps}
        onPointerEnter={schedule}
        onPointerLeave={keepPreview ? leave : close}
        onPointerCancel={close}
      >
        {children}
      </Tag>
      {open &&
        createPortal(
          <div
            ref={pop}
            className={cn(
              'fixed z-50 max-h-[calc(100vh-16px)] overflow-y-auto rounded-xl bg-popover p-2 shadow-xl ring-1 ring-foreground/15',
              !keepPreview && 'pointer-events-none',
              !pos && 'invisible',
            )}
            style={{ left: pos?.left ?? 0, top: pos?.top ?? 0 }}
            onPointerEnter={stay}
            onPointerLeave={leave}
          >
            {preview}
          </div>,
          document.body,
        )}
    </>
  )
}
