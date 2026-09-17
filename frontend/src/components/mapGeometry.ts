export interface Point { x: number; y: number }
export interface RoomBox extends Point { halfWidth: number; halfHeight: number }

export const ROOM_WIDTH = 176
export const ROOM_HEIGHT = 80

export function roomNameLines(name: string, capacity: number): string[] {
  const text = name.trim().replace(/\s+/g, ' ')
  if (text.length <= capacity) return [text]
  const space = text.lastIndexOf(' ', capacity)
  const split = space > 0 ? space : capacity
  const rest = text.slice(split).trimStart()
  return [text.slice(0, split), rest.length <= capacity ? rest : `${rest.slice(0, capacity - 1)}…`]
}

// Route along a rectilinear grid of room boundaries. Every segment is checked
// against every box, including the stair endpoints, so no line crosses a room.
export function stairRoute(from: RoomBox, to: RoomBox, rooms: RoomBox[]): Point[] {
  const clearance = 12
  const obstacles = rooms.map(room => ({ ...room,
    halfWidth: room.halfWidth + clearance, halfHeight: room.halfHeight + clearance,
  }))
  const ports = (room: RoomBox) => [-1, 1].map(side => ({
    x: room.x + side * (room.halfWidth + clearance), y: room.y,
  })).concat([-1, 1].map(side => ({ x: room.x, y: room.y + side * (room.halfHeight + clearance) })))
  const starts = ports(from)
  const ends = ports(to)
  const xs = [...new Set([...obstacles.flatMap(room => [room.x - room.halfWidth, room.x + room.halfWidth]),
    ...starts.map(p => p.x), ...ends.map(p => p.x)])].sort((a, b) => a - b)
  const ys = [...new Set([...obstacles.flatMap(room => [room.y - room.halfHeight, room.y + room.halfHeight]),
    ...starts.map(p => p.y), ...ends.map(p => p.y)])].sort((a, b) => a - b)
  const index = (point: Point) => ys.indexOf(point.y) * xs.length + xs.indexOf(point.x)
  const point = (id: number) => ({ x: xs[id % xs.length], y: ys[Math.floor(id / xs.length)] })
  const goals = new Set(ends.map(index))
  const distance = new Map(starts.map(p => [index(p), 0]))
  const previous = new Map<number, number>()
  const pending = starts.map(index)
  const heuristic = (id: number) => Math.min(...ends.map(end =>
    Math.abs(point(id).x - end.x) + Math.abs(point(id).y - end.y)))
  const visited = new Set<number>()
  while (pending.length) {
    pending.sort((a, b) => distance.get(b)! + heuristic(b) - distance.get(a)! - heuristic(a))
    const id = pending.pop()!
    if (visited.has(id)) continue
    visited.add(id)
    if (goals.has(id)) {
      const path = [point(id)]
      let cursor = id
      while (previous.has(cursor)) { cursor = previous.get(cursor)!; path.unshift(point(cursor)) }
      return [{ x: from.x + Math.sign(path[0].x - from.x) * from.halfWidth,
        y: from.y + Math.sign(path[0].y - from.y) * from.halfHeight },
      ...path, { x: to.x + Math.sign(path[path.length - 1].x - to.x) * to.halfWidth,
        y: to.y + Math.sign(path[path.length - 1].y - to.y) * to.halfHeight }]
    }
    const x = id % xs.length
    const y = Math.floor(id / xs.length)
    const neighbors = [x > 0 ? id - 1 : -1, x < xs.length - 1 ? id + 1 : -1,
      y > 0 ? id - xs.length : -1, y < ys.length - 1 ? id + xs.length : -1]
    const a = point(id)
    for (const next of neighbors) {
      if (next < 0 || visited.has(next)) continue
      const b = point(next)
      const blocked = obstacles.some(room => a.y === b.y
        ? a.y > room.y - room.halfHeight && a.y < room.y + room.halfHeight
          && Math.max(a.x, b.x) > room.x - room.halfWidth && Math.min(a.x, b.x) < room.x + room.halfWidth
        : a.x > room.x - room.halfWidth && a.x < room.x + room.halfWidth
          && Math.max(a.y, b.y) > room.y - room.halfHeight && Math.min(a.y, b.y) < room.y + room.halfHeight)
      if (blocked) continue
      const cost = distance.get(id)! + Math.abs(a.x - b.x) + Math.abs(a.y - b.y)
      if (cost >= (distance.get(next) ?? Infinity)) continue
      distance.set(next, cost)
      previous.set(next, id)
      pending.push(next)
    }
  }
  return []
}
