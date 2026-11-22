import type { MapState } from './MapPanel'
import { mapLevels, type MapLevel } from './mapLevels'
import { ROOM_HEIGHT, ROOM_WIDTH, type Point } from './mapGeometry'

const COLUMN_SPACING = 208
const ROW_SPACING = 116

const offsets: Record<string, Point> = {
  north: { x: 0, y: -1 }, south: { x: 0, y: 1 },
  east: { x: 1, y: 0 }, west: { x: -1, y: 0 },
  up: { x: 1, y: -1 }, down: { x: -1, y: 1 },
}

// This is a schematic of authorized connections, not authoritative coordinates.
// Keep every node distinct even when loops or vertical exits overlap on a grid.
export function layoutMap(map: MapState): Map<string, Point> {
  const positions = new Map<string, Point>()
  const occupied = new Set<string>()
  const adjacency = new Map<string, { id: string; offset: Point }[]>()
  for (const edge of map.exits) {
    const offset = offsets[edge.direction] ?? { x: 1, y: 0 }
    adjacency.set(edge.room_id, [...(adjacency.get(edge.room_id) ?? []), { id: edge.destination_room_id, offset }])
    adjacency.set(edge.destination_room_id, [...(adjacency.get(edge.destination_room_id) ?? []),
      { id: edge.room_id, offset: { x: -offset.x, y: -offset.y } }])
  }
  const place = (id: string, point: Point, step: Point) => {
    const key = `${point.x},${point.y}`
    if (occupied.has(key)) {
      // Open a row or column before the obstruction so the new connection stays
      // on its compass line and does not run through the room it would overlap.
      const axis = step.x === 0 ? 'y' : 'x'
      const direction = step[axis]
      occupied.clear()
      for (const placed of positions.values()) {
        if ((placed[axis] - point[axis]) * direction >= 0) placed[axis] += direction
        occupied.add(`${placed.x},${placed.y}`)
      }
    }
    positions.set(id, point)
    occupied.add(key)
  }
  for (const room of [...map.rooms].sort((a, b) => a.id.localeCompare(b.id))) {
    if (positions.has(room.id)) continue
    place(room.id, { x: positions.size * 2, y: 0 }, offsets.east)
    const queue = [room.id]
    for (let index = 0; index < queue.length; index += 1) {
      const id = queue[index]
      const origin = positions.get(id)!
      for (const neighbor of adjacency.get(id) ?? []) {
        if (positions.has(neighbor.id)) continue
        place(neighbor.id, { x: origin.x + neighbor.offset.x, y: origin.y + neighbor.offset.y }, neighbor.offset)
        queue.push(neighbor.id)
      }
    }
  }
  return new Map([...positions].map(([id, point]) => [id, { x: point.x * COLUMN_SPACING, y: point.y * ROW_SPACING }]))
}

export interface MapSceneLevel extends MapLevel {
  positions: Map<string, Point>
}

// Each horizontal component is anchored to an actual stair connection. Different
// components on the same floor must not inherit an unrelated staircase's origin.
export function buildMapScene(map: MapState, currentId: string, allLevels = false): MapSceneLevel[] {
  const levels = mapLevels(map, currentId, allLevels ? Infinity : 2)
  const placed = new Map<string, Point>()
  const depths = new Map(levels.flatMap(level => level.map.rooms.map(room => [room.id, level.depth] as const)))
  const stairs = map.exits.filter(edge => edge.direction === 'up' || edge.direction === 'down')
    .flatMap(edge => [edge, { room_id: edge.destination_room_id, destination_room_id: edge.room_id,
      direction: edge.direction === 'up' ? 'down' : 'up' }])
    .sort((a, b) => `${a.room_id}:${a.destination_room_id}`.localeCompare(`${b.room_id}:${b.destination_room_id}`))
  const scene = levels.map(level => {
    if (!level.depth) {
      const positions = layoutMap(level.map)
      for (const [id, point] of positions) placed.set(id, point)
      return { ...level, positions }
    }
    const positions = new Map<string, Point>()
    const pending = new Set(level.map.rooms.map(room => room.id))
    const step = Math.sign(level.depth)
    for (const room of [...level.map.rooms].sort((a, b) => a.id.localeCompare(b.id))) {
      if (!pending.has(room.id)) continue
      const component = mapLevels(level.map, room.id)[0].map
      const local = layoutMap(component)
      const anchor = stairs.find(edge => local.has(edge.destination_room_id)
        && depths.get(edge.room_id) === level.depth - step && placed.has(edge.room_id))
      // All preview components originate from a visited stair in the preceding level.
      if (!anchor) continue
      const parent = placed.get(anchor.room_id)!
      const child = local.get(anchor.destination_room_id)!
      const offset = { x: parent.x - child.x - step * ROOM_WIDTH / 8,
        y: parent.y - child.y - step * ROOM_HEIGHT / 4 }
      // Conflicting stair attachments can place separate components on top of one
      // another. Preserve their internal connections and shift only that component.
      while ([...local.values()].some(point => [...positions.values()].some(other =>
        Math.abs(point.x + offset.x - other.x) < ROOM_WIDTH + 8
          && Math.abs(point.y + offset.y - other.y) < ROOM_HEIGHT + 8))) offset.x += COLUMN_SPACING
      for (const [id, point] of local) {
        const translated = { x: point.x + offset.x, y: point.y + offset.y }
        positions.set(id, translated)
        placed.set(id, translated)
        pending.delete(id)
      }
    }
    return { ...level, positions }
  })
  const origin = placed.get(currentId)
  if (!allLevels || !origin) return scene
  return scene.map(({ depth, map: levelMap, positions }) => {
    // Undo the visual floor offset before measuring horizontal distance.
    const withinRadius = new Map([...positions].filter(([, point]) => Math.hypot(
      (point.x - origin.x + depth * ROOM_WIDTH / 8) / COLUMN_SPACING,
      (point.y - origin.y + depth * ROOM_HEIGHT / 4) / ROW_SPACING,
    ) <= 10))
    return { depth, positions: withinRadius, map: {
      rooms: levelMap.rooms.filter(room => withinRadius.has(room.id)),
      exits: levelMap.exits.filter(edge => withinRadius.has(edge.room_id) && withinRadius.has(edge.destination_room_id)),
    } }
  }).filter(level => level.positions.size > 0)
}
