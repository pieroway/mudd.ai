import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'
import type { MapState } from './MapPanel'

interface RoomFrame { screen: DOMMatrix; opacity: string }

// Animate only authoritative, directly connected vertical moves. Screen-space
// snapshots account for changes in diagram origin, fitted zoom, and viewport.
export function useFloorTransition(ref: RefObject<SVGSVGElement>, roomId: string | undefined, map: MapState | undefined) {
  const previous = useRef<{ roomId: string; map: MapState; rooms: Map<string, RoomFrame> }>()
  const running = useRef<Animation[]>([])
  const stop = () => { running.current.forEach(animation => animation.cancel()); running.current = [] }

  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const changed = () => { if (preference?.matches) stop() }
    preference?.addEventListener('change', changed)
    return () => { stop(); preference?.removeEventListener('change', changed) }
  }, [])

  useLayoutEffect(() => {
    const svg = ref.current
    if (!roomId || !map || !svg) { stop(); previous.current = undefined; return }
    // jsdom and older browsers can still render an instant floor change.
    if (!svg.getScreenCTM || !svg.animate) return
    const old = previous.current
    const moved = old && old.roomId !== roomId
    const edge = moved ? [...old.map.exits, ...map.exits].find(exit =>
      exit.room_id === old.roomId && exit.destination_room_id === roomId
      && (exit.direction === 'up' || exit.direction === 'down')) : undefined
    const animate = !!edge && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (moved) stop()
    const rooms = new Map<string, RoomFrame>()
    const effects: (() => void)[] = []
    for (const layer of svg.querySelectorAll<SVGGElement>('[data-level]')) {
      const opacity = getComputedStyle(layer).opacity
      const elements = [...layer.querySelectorAll<SVGGElement>('[data-room]')]
      const oldLayer = elements.map(el => old?.rooms.get(el.dataset.room!)).find(Boolean)
      if (animate) effects.push(() => {
        running.current.push(layer.animate([{ opacity: oldLayer?.opacity ?? '0' }, { opacity }],
          { duration: 260, easing: 'ease-out' }))
      })
      for (const element of elements) {
        const screen = element.getScreenCTM()
        const parent = layer.getScreenCTM()
        if (!screen || !parent) continue
        rooms.set(element.dataset.room!, { screen, opacity })
        if (!animate) continue
        const target = parent.inverse().multiply(screen)
        const prior = old?.rooms.get(element.dataset.room!)
        // On mobile there are no ghosts: bring the new floor in from the same
        // upper-left/lower-right direction used by the desktop floor stack.
        const start = prior ? parent.inverse().multiply(prior.screen)
          : target.translate(edge.direction === 'up' ? -22 : 22, edge.direction === 'up' ? -20 : 20)
        effects.push(() => {
          running.current.push(element.animate([
            { transform: start.toString() }, { transform: target.toString() },
          ], { duration: 260, easing: 'ease-out' }))
        })
      }
    }
    previous.current = { roomId, map, rooms }
    if (animate) {
      effects.forEach(start => start())
      const animations = running.current
      void Promise.allSettled(animations.map(animation => animation.finished)).then(() => {
        if (running.current === animations) running.current = []
      })
    }
  })
}