import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

/**
 * One look for every hover text: elements that carry a plain `title` get the same light pop-up as the board's
 * tooltips instead of the browser's own. The title moves to data-title on first hover so the browser's
 * tooltip never shows; the text is read from there afterwards.
 */
export function TitleTips() {
  const [tip, setTip] = useState<{ text: string; rect: DOMRect } | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const current = useRef<Element | null>(null)
  const pop = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  useEffect(() => {
    const find = (el: EventTarget | null): Element | null => {
      let n = el instanceof Element ? el : null
      while (n && n !== document.body) {
        if (n.hasAttribute('title') || n.hasAttribute('data-title')) return n
        n = n.parentElement
      }
      return null
    }
    const over = (e: PointerEvent) => {
      // Inside a board tooltip's trigger, that tooltip already explains it: no second pop-up on top.
      const inTip = e.target instanceof Element && e.target.closest('[data-slot=tooltip-trigger]')
      const el = inTip ? null : find(e.target)
      if (el === current.current) return
      current.current = el
      window.clearTimeout(timer.current)
      setTip(null)
      if (!el) return
      const title = el.getAttribute('title')
      if (title !== null) {
        el.setAttribute('data-title', title)
        el.removeAttribute('title')
      }
      const text = el.getAttribute('data-title') ?? ''
      if (!text.trim()) return
      timer.current = window.setTimeout(() => setTip({ text, rect: el.getBoundingClientRect() }), 150)
    }
    const hide = () => {
      current.current = null
      window.clearTimeout(timer.current)
      setTip(null)
    }
    document.addEventListener('pointerover', over)
    document.addEventListener('pointerdown', hide)
    window.addEventListener('scroll', hide, true)
    return () => {
      document.removeEventListener('pointerover', over)
      document.removeEventListener('pointerdown', hide)
      window.removeEventListener('scroll', hide, true)
    }
  }, [])

  useEffect(() => {
    if (!tip || !pop.current) return setPos(null)
    const r = pop.current.getBoundingClientRect()
    let top = tip.rect.bottom + 6
    if (top + r.height > innerHeight - 8) top = tip.rect.top - r.height - 6
    const left = Math.max(8, Math.min(tip.rect.left + tip.rect.width / 2 - r.width / 2, innerWidth - r.width - 8))
    setPos({ left, top })
  }, [tip])

  if (!tip) return null
  return createPortal(
    <div
      ref={pop}
      role="tooltip"
      className="pointer-events-none fixed z-[60] max-w-72 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-snug whitespace-pre-line text-slate-700 shadow-xl"
      style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999 }}
    >
      {tip.text}
    </div>,
    document.body,
  )
}
