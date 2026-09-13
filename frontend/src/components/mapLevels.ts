import type { MapState } from './MapPanel'

export interface MapLevel {
  depth: number
  map: MapState
}

// A horizontal connected component is one neighborhood on one floor. Expand
// monotonically above/below it: going up then down must not reveal a remote floor 0.
export function mapLevels(map: MapState, currentId: string): MapLevel[] {
  const neighbors = new Map(map.rooms.map(room => [room.id, new Set<string>()]))
  const horizontal = map.exits.filter(edge => edge.direction !== 'up' && edge.direction !== 'down')
  for (const edge of horizontal) {
    neighbors.get(edge.room_id)?.add(edge.destination_room_id)
    neighbors.get(edge.destination_room_id)?.add(edge.room_id)
  }
  const component = new Map<string, number>()
  let next = 0
  for (const room of map.rooms) {
    if (component.has(room.id)) continue
    const queue = [room.id]
    component.set(room.id, next)
    for (let i = 0; i < queue.length; i += 1) {
      for (const id of neighbors.get(queue[i]) ?? []) {
        if (component.has(id)) continue
        component.set(id, next)
        queue.push(id)
      }
    }
    next += 1
  }
  const origin = component.get(currentId)
  if (origin === undefined) return []
  const vertical = new Map<number, { destination: number; step: number }[]>()
  for (const edge of map.exits) {
    if (edge.direction !== 'up' && edge.direction !== 'down') continue
    const from = component.get(edge.room_id)!
    const to = component.get(edge.destination_room_id)!
    if (from === to) continue
    const step = edge.direction === 'up' ? 1 : -1
    vertical.set(from, [...(vertical.get(from) ?? []), { destination: to, step }])
    vertical.set(to, [...(vertical.get(to) ?? []), { destination: from, step: -step }])
  }
  const depths = new Map([[origin, 0]])
  const queue = [origin]
  for (let i = 0; i < queue.length; i += 1) {
    const from = queue[i]
    const depth = depths.get(from)!
    if (Math.abs(depth) === 2) continue
    for (const edge of vertical.get(from) ?? []) {
      if (depth && Math.sign(depth) !== edge.step) continue
      if (depths.has(edge.destination)) continue
      depths.set(edge.destination, depth + edge.step)
      queue.push(edge.destination)
    }
  }
  return [0, 1, -1, 2, -2].flatMap(depth => {
    const rooms = map.rooms.filter(room => depths.get(component.get(room.id)!) === depth)
    if (!rooms.length) return []
    const ids = new Set(rooms.map(room => room.id))
    return [{ depth, map: { rooms, exits: horizontal.filter(edge => ids.has(edge.room_id) && ids.has(edge.destination_room_id)) } }]
  })
}
