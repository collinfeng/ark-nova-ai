import { useEffect, useRef, useState, type RefObject } from 'react'
import type { Card, CardStatus } from '@/api/types'
import { CardTile } from './CardTile'

/** The printed card's own width; smaller cards are the same card drawn smaller (hover shows it full size). */
export const CARD_W = 168
export const CARD_H = 236

/** A card at `scale` of its printed size, keeping its layout, with the full-size hover preview. */
export function ScaledCard({ card, status, scale, dim, className }: { card: Card; status?: CardStatus | null; scale: number; dim?: boolean; className?: string }) {
  return (
    <div className={className} style={{ width: CARD_W * scale, height: CARD_H * scale, flexShrink: 0 }}>
      <div style={{ zoom: scale }}>
        <CardTile card={card} status={status} dim={dim} />
      </div>
    </div>
  )
}

/** The width of an element, kept up to date. */
export function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const o = new ResizeObserver(() => setW(el.clientWidth))
    o.observe(el)
    setW(el.clientWidth)
    return () => o.disconnect()
  }, [ref])
  return w
}

export function useMeasure<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const width = useWidth(ref)
  return [ref, width] as const
}
