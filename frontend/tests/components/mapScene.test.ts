import { describe, expect, it } from 'vitest'
import { buildMapScene, layoutMap } from '../../src/components/mapScene'
import { ROOM_HEIGHT, ROOM_WIDTH } from '../../src/components/mapGeometry'
import type { MapState } from '../../src/components/MapPanel'

const floors: MapState = {
  rooms: ['hall', 'east', 'upper', 'guest', 'attic', 'cellar', 'tunnel', 'remote', 'other_upper'].map(id => ({ id, name: id })),
  exits: [
    { room_id: 'hall', direction: 'east', destination_room_id: 'east' },
    { room_id: 'hall', direction: 'up', destination_room_id: 'upper' },
    { room_id: 'upper', direction: 'east', destination_room_id: 'guest' },
    { room_id: 'upper', direction: 'up', destination_room_id: 'attic' },
    { room_id: 'hall', direction: 'down', destination_room_id: 'cellar' },
    { room_id: 'cellar', direction: 'down', destination_room_id: 'tunnel' },
    { room_id: 'east', direction: 'up', destination_room_id: 'other_upper' },
  ],
}

describe('Overlapping floors', () => {
  it('anchors each floor to its stair room with cumulative one-eighth/one-quarter offsets', () => {
    const scene = buildMapScene(floors, 'hall')
    const positions = new Map(scene.flatMap(level => [...level.positions]))
    const hall = positions.get('hall')!
    for (const [id, depth] of [['upper', 1], ['attic', 2], ['cellar', -1], ['tunnel', -2]] as const) {
      expect(positions.get(id)).toEqual({ x: hall.x - depth * ROOM_WIDTH / 8, y: hall.y - depth * ROOM_HEIGHT / 4 })
    }
    expect(scene[0].positions).toEqual(layoutMap(scene[0].map))
    expect(positions.has('remote')).toBe(false)
    expect(positions.get('guest')!.x - positions.get('upper')!.x).toBe(208)
  })

  it('anchors disconnected neighborhoods separately, including one-way stair edges', () => {
    const scene = buildMapScene(floors, 'hall')
    const positions = new Map(scene.flatMap(level => [...level.positions]))
    const east = positions.get('east')!
    // This component would coincide with Guest Room; move it as one unit instead
    // of hiding a discovered room underneath another room on the same floor.
    expect(positions.get('other_upper')!.y).toBe(east.y - ROOM_HEIGHT / 4)
    const upper = scene.find(level => level.depth === 1)!
    expect(new Set([...upper.positions.values()].map(p => `${p.x},${p.y}`)).size).toBe(upper.map.rooms.length)
    const descending = buildMapScene(floors, 'upper')
    expect(descending.find(level => level.depth === -1)!.positions.has('hall')).toBe(true)
  })

  it('keeps layout stable when the server changes room and exit order', () => {
    const reversed = { rooms: [...floors.rooms].reverse(), exits: [...floors.exits].reverse() }
    // Compare a linear stair chain without horizontal ambiguity.
    const chain = { rooms: floors.rooms.filter(r => ['hall', 'upper', 'attic'].includes(r.id)),
      exits: floors.exits.filter(e => e.direction === 'up' && ['hall', 'upper'].includes(e.room_id)) }
    const a = buildMapScene(chain, 'hall')
    const b = buildMapScene({ rooms: [...chain.rooms].reverse(), exits: [...chain.exits].reverse() }, 'hall')
    expect(b.map(level => [...level.positions])).toEqual(a.map(level => [...level.positions]))
    expect(buildMapScene(reversed, 'missing')).toEqual([])
  })
})
