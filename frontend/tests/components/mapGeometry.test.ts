import { describe, expect, it } from 'vitest'
import { roomNameLines, stairRoute, type RoomBox } from '../../src/components/mapGeometry'

describe('Map readability', () => {
  it('uses two lines to distinguish rooms with the same name prefix', () => {
    expect(roomNameLines('Wet Bins Chamber East', 15)).toEqual(['Wet Bins', 'Chamber East'])
    expect(roomNameLines('Wet Bins Chamber West', 15)).toEqual(['Wet Bins', 'Chamber West'])
    expect(roomNameLines('Inn', 20)).toEqual(['Inn'])
    expect(roomNameLines('Old Passage', 10)).toEqual(['Old', 'Passage'])
    expect(roomNameLines('A very long room name that cannot fit in two lines', 15)[1]).toMatch(/…$/)
  })

  it('routes stairs around intervening rooms with only right-angle segments', () => {
    const box = (x: number, y: number): RoomBox => ({ x, y, halfWidth: 88, halfHeight: 40 })
    const from = box(0, 232)
    const to = box(208, -232)
    const rooms = [from, to, box(0, 116), box(0, 0), box(208, 0), box(208, 116)]
    const path = stairRoute(from, to, rooms)
    expect(path.length).toBeGreaterThan(2)
    for (let i = 1; i < path.length; i += 1) {
      const a = path[i - 1]
      const b = path[i]
      expect(a.x === b.x || a.y === b.y).toBe(true)
      for (const room of rooms) {
        const crosses = a.y === b.y
          ? a.y > room.y - room.halfHeight && a.y < room.y + room.halfHeight
            && Math.max(a.x, b.x) > room.x - room.halfWidth && Math.min(a.x, b.x) < room.x + room.halfWidth
          : a.x > room.x - room.halfWidth && a.x < room.x + room.halfWidth
            && Math.max(a.y, b.y) > room.y - room.halfHeight && Math.min(a.y, b.y) < room.y + room.halfHeight
        expect(crosses).toBe(false)
      }
    }
  })

  it('connects vertically aligned stairs directly when the gap is clear', () => {
    const from = { x: 0, y: 0, halfWidth: 88, halfHeight: 40 }
    const to = { ...from, y: -160 }
    const path = stairRoute(from, to, [from, to])
    expect(path.length).toBeGreaterThan(1)
    expect(path.every(point => point.x === 0)).toBe(true)
    expect(path[0].y).toBe(-40)
    expect(path[path.length - 1].y).toBe(-120)
  })
})
