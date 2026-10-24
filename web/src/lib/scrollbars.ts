/**
 * Shows the scrollbar of a `.scroll-area` while the pointer moves over it and hides it again 1.2 s after
 * the pointer stops, leaves the window or the page loses focus. Plain :hover is not enough: it can stay
 * stuck when the pointer leaves quickly or a popup opens over the area.
 */
export function watchScrollbars(): () => void {
  let active: Element | null = null
  let timer: number | undefined
  const clear = () => {
    window.clearTimeout(timer)
    active?.removeAttribute('data-active')
    active = null
  }
  const move = (e: PointerEvent) => {
    const area = e.target instanceof Element ? e.target.closest('.scroll-area') : null
    if (area !== active) clear()
    if (!area) return
    active = area
    area.setAttribute('data-active', '')
    window.clearTimeout(timer)
    timer = window.setTimeout(clear, 1200)
  }
  document.addEventListener('pointermove', move, { passive: true })
  document.addEventListener('pointerleave', clear)
  document.documentElement.addEventListener('mouseleave', clear)
  window.addEventListener('blur', clear)
  return () => {
    clear()
    document.removeEventListener('pointermove', move)
    document.removeEventListener('pointerleave', clear)
    document.documentElement.removeEventListener('mouseleave', clear)
    window.removeEventListener('blur', clear)
  }
}
