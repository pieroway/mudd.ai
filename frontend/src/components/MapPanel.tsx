import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClientState } from './InventoryPanel'

export interface MapState {
  rooms: { id: string; name: string }[]
  exits: { room_id: string; direction: string; destination_room_id: string }[]
}

export function isMapState(value: unknown): value is MapState {
  if (!value || typeof value !== 'object') return false
  const map = value as Partial<MapState>
  if (!Array.isArray(map.rooms) || !map.rooms.every(room => room
    && typeof room.id === 'string' && typeof room.name === 'string')) return false
  const ids = new Set(map.rooms.map(room => room.id))
  return ids.size === map.rooms.length && Array.isArray(map.exits) && map.exits.every(edge => edge
    && typeof edge.direction === 'string' && ids.has(edge.room_id) && ids.has(edge.destination_room_id))
}

type Point = { x: number; y: number }
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
  const place = (id: string, point: Point) => {
    const candidate = { ...point }
    while (occupied.has(`${candidate.x},${candidate.y}`)) candidate.x += 1
    positions.set(id, candidate)
    occupied.add(`${candidate.x},${candidate.y}`)
  }
  for (const room of [...map.rooms].sort((a, b) => a.id.localeCompare(b.id))) {
    if (positions.has(room.id)) continue
    place(room.id, { x: positions.size * 2, y: 0 })
    const queue = [room.id]
    for (let index = 0; index < queue.length; index += 1) {
      const id = queue[index]
      const origin = positions.get(id)!
      for (const neighbor of adjacency.get(id) ?? []) {
        if (positions.has(neighbor.id)) continue
        place(neighbor.id, { x: origin.x + neighbor.offset.x, y: origin.y + neighbor.offset.y })
        queue.push(neighbor.id)
      }
    }
  }
  return new Map([...positions].map(([id, point]) => [id, { x: point.x * 180, y: point.y * 110 }]))
}

export default function MapPanel({ state, connected, expanded, onExpand }: {
  state?: ClientState; connected: boolean; expanded: boolean; onExpand: () => void
}) {
  const map = isMapState(state?.map) ? state.map : undefined
  const positions = useMemo(() => layoutMap(map ?? { rooms: [], exits: [] }), [map])
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const [selected, setSelected] = useState<string>()
  const viewportRef = useRef<SVGSVGElement>(null)
  const [viewport, setViewport] = useState({ width: 400, height: 280 })
  const ready = connected && !!map
  useEffect(() => {
    const svg = viewportRef.current
    if (!svg || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) setViewport({ width, height })
    })
    observer.observe(svg)
    return () => observer.disconnect()
  }, [ready])
  const drag = useRef<{ x: number; y: number; pan: Point }>()
  const current = positions.get(state?.room_id ?? '') ?? { x: 0, y: 0 }
  const width = viewport.width / zoom
  const height = viewport.height / zoom
  const selectedRoom = map?.rooms.find(room => room.id === selected)
    ?? map?.rooms.find(room => room.id === state?.room_id)
  const names = new Map(map?.rooms.map(room => [room.id, room.name]))
  const drawn = new Set<string>()
  const edges = map?.exits.filter(edge => {
    const key = JSON.stringify([edge.room_id, edge.destination_room_id].sort())
    if (drawn.has(key)) return false
    drawn.add(key)
    return true
  }) ?? []

  return <aside id="map-panel" className="context-panel map-panel" aria-labelledby="map-heading" data-testid="map-panel">
    <div className="map-heading"><h3 id="map-heading">Discovered world</h3>
      <button type="button" onClick={onExpand} aria-expanded={expanded}>{expanded ? 'Collapse map' : 'Expand map'}</button></div>
    {!connected ? <p role="status">Disconnected. Reconnect to refresh your map.</p>
      : !map ? <p role="status">Waiting for map…</p>
        : <>
          <div className="map-controls" role="group" aria-label="Map controls">
            <button type="button" aria-label="Zoom in" disabled={zoom >= 3} onClick={() => setZoom(value => Math.min(3, value * 1.25))}>+</button>
            <button type="button" aria-label="Zoom out" disabled={zoom <= 0.25} onClick={() => setZoom(value => Math.max(0.25, value / 1.25))}>−</button>
            <button type="button" onClick={() => { setPan({ x: 0, y: 0 }); setZoom(1); setSelected(undefined) }}>Center on me</button>
            <button type="button" aria-label="Pan north" onClick={() => setPan(p => ({ ...p, y: p.y - 80 / zoom }))}>↑</button>
            <button type="button" aria-label="Pan west" onClick={() => setPan(p => ({ ...p, x: p.x - 80 / zoom }))}>←</button>
            <button type="button" aria-label="Pan east" onClick={() => setPan(p => ({ ...p, x: p.x + 80 / zoom }))}>→</button>
            <button type="button" aria-label="Pan south" onClick={() => setPan(p => ({ ...p, y: p.y + 80 / zoom }))}>↓</button>
          </div>
          <svg ref={viewportRef} className="map-viewport" role="group" aria-label="Discovered rooms and connections"
            viewBox={`${current.x + pan.x - width / 2} ${current.y + pan.y - height / 2} ${width} ${height}`}
            onPointerDown={event => {
              if (event.button !== 0 || (event.target as Element).closest('[data-room]')) return
              event.currentTarget.setPointerCapture(event.pointerId)
              drag.current = { x: event.clientX, y: event.clientY, pan }
            }}
            onPointerMove={event => {
              if (!drag.current) return
              const bounds = event.currentTarget.getBoundingClientRect()
              const scale = Math.max(width / bounds.width, height / bounds.height)
              setPan({ x: drag.current.pan.x - (event.clientX - drag.current.x) * scale,
                y: drag.current.pan.y - (event.clientY - drag.current.y) * scale })
            }}
            onPointerUp={() => { drag.current = undefined }}
            onPointerCancel={() => { drag.current = undefined }}
            onLostPointerCapture={() => { drag.current = undefined }}>
            {edges.map(edge => {
              const from = positions.get(edge.room_id)!
              const to = positions.get(edge.destination_room_id)!
              return <line key={`${edge.room_id}:${edge.direction}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} className="map-edge" />
            })}
            {map.rooms.map(room => {
              const point = positions.get(room.id)!
              const here = room.id === state?.room_id
              return <g key={room.id} data-room={room.id} role="button" tabIndex={0}
                aria-label={`${room.name}${here ? ', you are here' : ''}`} aria-pressed={selectedRoom?.id === room.id}
                className={`map-room ${here ? 'map-current' : ''}`} transform={`translate(${point.x}, ${point.y})`}
                onClick={() => setSelected(room.id)} onKeyDown={event => {
                  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(room.id) }
                }}>
                <title>{room.name}{here ? ' — You are here' : ''}</title>
                <rect x={-76} y={-26} width={152} height={52} rx={8} />
                <text textAnchor="middle" y={here ? -3 : 5}>{room.name.length > 19 ? `${room.name.slice(0, 18)}…` : room.name}</text>
                {here && <text textAnchor="middle" y={16} className="map-here">You are here</text>}
              </g>
            })}
          </svg>
          {selectedRoom && <details className="map-details" key={selectedRoom.id} open={selected !== undefined}>
            <summary>{selectedRoom.name} — known exits</summary>
            <ul>{map.exits.filter(edge => edge.room_id === selectedRoom.id).map(edge =>
              <li key={edge.direction}>{edge.direction} → {names.get(edge.destination_room_id)}</li>)}</ul>
          </details>}
          <p className="map-note">{map.rooms.length} discovered {map.rooms.length === 1 ? 'room' : 'rooms'}. Drag to pan; select rooms for exits.</p>
        </>}
  </aside>
}
