import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClientState } from './InventoryPanel'
import { mapLevels } from './mapLevels'
import { ROOM_HEIGHT, ROOM_WIDTH, roomNameLines, stairRoute } from './mapGeometry'

export interface MapState {
  rooms: { id: string; name: string; building_id?: string | null; has_up?: boolean; has_down?: boolean }[]
  exits: { room_id: string; direction: string; destination_room_id: string }[]
}

export function isMapState(value: unknown): value is MapState {
  if (!value || typeof value !== 'object') return false
  const map = value as Partial<MapState>
  if (!Array.isArray(map.rooms) || !map.rooms.every(room => room
    && typeof room.id === 'string' && typeof room.name === 'string'
    && (room.has_up === undefined || typeof room.has_up === 'boolean')
    && (room.has_down === undefined || typeof room.has_down === 'boolean')
    && (room.building_id === undefined || typeof room.building_id === 'string' || room.building_id === null))) return false
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
  return new Map([...positions].map(([id, point]) => [id, { x: point.x * 208, y: point.y * 116 }]))
}

export default function MapPanel({ state, connected, expanded, onExpand }: {
  state?: ClientState; connected: boolean; expanded: boolean; onExpand: () => void
}) {
  const map = isMapState(state?.map) ? state.map : undefined
  const levels = useMemo(() => map ? mapLevels(map, state?.room_id ?? '') : [], [map, state?.room_id])
  const visibleMap = levels[0]?.map ?? { rooms: [], exits: [] }
  const scene = useMemo(() => {
    const positions = layoutMap(levels[0]?.map ?? { rooms: [], exits: [] })
    const points = [...positions.values()]
    const top = Math.min(0, ...points.map(point => point.y))
    const bottom = Math.max(0, ...points.map(point => point.y))
    const centerX = points.length ? (Math.min(...points.map(point => point.x)) + Math.max(...points.map(point => point.x))) / 2 : 0
    const boundary = { above: top - 100, below: bottom + 100 }
    const placedRooms = new Map(positions)
    return levels.map(level => {
      const scale = level.depth === 0 ? 1 : Math.abs(level.depth) === 1 ? 0.8 : 0.65
      if (!level.depth) return { ...level, positions, scale, label: { x: centerX, y: top - 62 } }
      const local = layoutMap(level.map)
      const values = [...local.values()]
      const minY = Math.min(...values.map(point => point.y))
      const maxY = Math.max(...values.map(point => point.y))
      const middleX = (Math.min(...values.map(point => point.x)) + Math.max(...values.map(point => point.x))) / 2
      const attachments = (map?.exits ?? []).flatMap(edge => {
        if (edge.direction !== 'up' && edge.direction !== 'down') return []
        const parent = placedRooms.get(edge.room_id)
        const child = local.get(edge.destination_room_id)
        return parent && child ? [parent.x - child.x * scale] : []
      })
      attachments.sort((a, b) => a - b)
      const offsetX = attachments.length ? attachments[Math.floor(attachments.length / 2)] : centerX - middleX * scale
      const y = level.depth > 0 ? boundary.above - (maxY - minY) * scale - ROOM_HEIGHT * scale / 2
        : boundary.below + ROOM_HEIGHT * scale / 2
      const placed = new Map([...local].map(([id, point]) => [id, {
        x: offsetX + point.x * scale,
        y: y + (point.y - minY) * scale,
      }]))
      for (const [id, point] of placed) placedRooms.set(id, point)
      if (level.depth > 0) boundary.above = y - ROOM_HEIGHT * scale / 2 - 60
      else boundary.below = y + (maxY - minY) * scale + ROOM_HEIGHT * scale / 2 + 60
      return { ...level, positions: placed, scale, label: { x: offsetX + middleX * scale, y: y - ROOM_HEIGHT * scale / 2 - 22 } }
    })
  }, [levels, map])
  const positions = scene[0]?.positions ?? new Map<string, Point>()
  const [nearby, setNearby] = useState(() => window.localStorage.getItem('mudd-map-nearby') !== 'false')
  useEffect(() => { window.localStorage.setItem('mudd-map-nearby', String(nearby)) }, [nearby])
  const [mobile, setMobile] = useState(() => window.innerWidth <= 640)
  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 640)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  const showNearby = nearby && !mobile
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const [fitted, setFitted] = useState(false)
  const [selected, setSelected] = useState<string>()
  const [hovered, setHovered] = useState<string>()
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
  const displayed = scene.filter(level => showNearby || level.depth === 0)
  const displayedRooms = displayed.flatMap(level => level.map.rooms)
  const selectedRoom = displayedRooms.find(room => room.id === selected)
    ?? visibleMap.rooms.find(room => room.id === state?.room_id)
  const names = new Map(map?.rooms.map(room => [room.id, room.name]))
  const allPositions = new Map(displayed.flatMap(level => [...level.positions]))
  const depths = new Map(displayed.flatMap(level => level.map.rooms.map(room => [room.id, level.depth] as const)))
  const geometry = useMemo(() => {
    const shown = scene.filter(level => showNearby || level.depth === 0)
    const boxes = new Map(shown.flatMap(level => [...level.positions].map(([id, point]) => [id, {
      ...point, halfWidth: ROOM_WIDTH * level.scale / 2, halfHeight: ROOM_HEIGHT * level.scale / 2,
    }] as const)))
    const drawn = new Set<string>()
    const routes = (map?.exits ?? []).flatMap(edge => {
      if (!showNearby || (edge.direction !== 'up' && edge.direction !== 'down')) return []
      const key = [edge.room_id, edge.destination_room_id].sort().join(':')
      const from = boxes.get(edge.room_id)
      const to = boxes.get(edge.destination_room_id)
      if (!from || !to || drawn.has(key) || shown.some(level =>
        level.positions.has(edge.room_id) && level.positions.has(edge.destination_room_id))) return []
      drawn.add(key)
      return [{ key, points: stairRoute(from, to, [...boxes.values()]) }]
    })
    const points = [...boxes.values()].flatMap(box => [
      { x: box.x - box.halfWidth, y: box.y - box.halfHeight },
      { x: box.x + box.halfWidth, y: box.y + box.halfHeight },
    ]).concat(routes.flatMap(route => route.points), shown.map(level => level.label))
    const left = Math.min(0, ...points.map(p => p.x))
    const right = Math.max(0, ...points.map(p => p.x))
    const top = Math.min(0, ...points.map(p => p.y))
    const bottom = Math.max(0, ...points.map(p => p.y))
    return { routes, left, right, top, bottom }
  }, [scene, showNearby, map])
  const fitZoom = Math.min(1, (viewport.width - Math.min(96, viewport.width * 0.25)) / Math.max(1, geometry.right - geometry.left),
    (viewport.height - Math.min(96, viewport.height * 0.25)) / Math.max(1, geometry.bottom - geometry.top))
  const displayZoom = fitted ? fitZoom : zoom
  const width = viewport.width / displayZoom
  const height = viewport.height / displayZoom
  const center = fitted ? { x: (geometry.left + geometry.right) / 2, y: (geometry.top + geometry.bottom) / 2 }
    : { x: current.x + pan.x, y: current.y + pan.y }
  const manualView = () => {
    setFitted(false)
    setZoom(displayZoom)
    setPan({ x: center.x - current.x, y: center.y - current.y })
  }
  const priority = (id: string) => id === hovered || id === selected ? 0 : id === state?.room_id ? 1 : 2
  const scales = new Map(displayed.flatMap(level => level.map.rooms.map(room => [room.id, level.scale] as const)))
  const labelWidthFor = (id: string) => Math.max(48, Math.min(160, ROOM_WIDTH * (scales.get(id) ?? 1) * displayZoom - 12))
  const labelBoxes: { x: number; y: number; width: number }[] = []
  const labels = new Set<string>()
  for (const room of [...displayedRooms].sort((a, b) => priority(a.id) - priority(b.id))) {
    const point = allPositions.get(room.id)!
    if (displayZoom < 0.2 || (priority(room.id) === 2 && displayZoom < (depths.get(room.id) ? 0.6 : 0.45))) continue
    const box = { x: point.x * displayZoom, y: point.y * displayZoom, width: labelWidthFor(room.id) }
    if (labelBoxes.some(other => Math.abs(other.x - box.x) < (other.width + box.width) / 2 + 8 && Math.abs(other.y - box.y) < 38)) continue
    labels.add(room.id)
    labelBoxes.push(box)
  }

  const renderLevel = (level: typeof scene[number]) => {
    const drawn = new Set<string>()
    const ghost = level.depth !== 0
    return <g key={level.depth} data-level={level.depth} className={ghost ? 'map-ghost-layer' : 'map-main-layer'}>
      {level.map.exits.map(edge => {
        const key = [edge.room_id, edge.destination_room_id].sort().join(':')
        if (drawn.has(key)) return null
        drawn.add(key)
        const from = level.positions.get(edge.room_id)!
        const to = level.positions.get(edge.destination_room_id)!
        return <path key={key} d={`M ${from.x} ${from.y} H ${(from.x + to.x) / 2} V ${to.y} H ${to.x}`}
          className="map-edge" vectorEffect="non-scaling-stroke" fill="none" />
      })}
      {level.map.rooms.map(room => {
        const point = level.positions.get(room.id)!
        const here = room.id === state?.room_id
        const up = room.has_up ?? map?.exits.some(edge => edge.room_id === room.id && edge.direction === 'up')
        const down = room.has_down ?? map?.exits.some(edge => edge.room_id === room.id && edge.direction === 'down')
        const exits = [up ? 'Up' : '', down ? 'Down' : ''].filter(Boolean)
        const badgeOffset = ROOM_HEIGHT * level.scale * displayZoom < 76 ? 18 / displayZoom : 0
        const labelWidth = labelWidthFor(room.id)
        const characters = Math.max(3, Math.floor(labelWidth / 7.2))
        const lines = roomNameLines(room.name, characters)
        return <g key={room.id} data-room={room.id} role="button" tabIndex={0}
          aria-label={`${room.name}${here ? ', you are here' : ''}${ghost ? `, level ${level.depth > 0 ? '+' : ''}${level.depth}` : ''}`}
          aria-pressed={selectedRoom?.id === room.id}
          className={`map-room ${here ? 'map-current' : ''}`}
          transform={`translate(${point.x}, ${point.y})`}
          onMouseEnter={() => setHovered(room.id)} onMouseLeave={() => setHovered(undefined)}
          onFocus={() => setHovered(room.id)} onBlur={() => setHovered(undefined)}
          onClick={() => setSelected(room.id)} onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(room.id) }
          }}>
          <title>{room.name}{here ? ' — You are here' : ''}{exits.length ? ` — ${exits.join(' and ')} exits` : ''}</title>
          <rect className="map-room-box" x={-ROOM_WIDTH * level.scale / 2} y={-ROOM_HEIGHT * level.scale / 2}
            width={ROOM_WIDTH * level.scale} height={ROOM_HEIGHT * level.scale} rx={5} vectorEffect="non-scaling-stroke" />
          {labels.has(room.id) && <g className="map-label" transform={`scale(${1 / displayZoom})`}>
            <rect className="map-label-background" x={-labelWidth / 2} y={-17} width={labelWidth} height={34} rx={3} />
            <text textAnchor="middle">{lines.map((line, index) =>
              <tspan key={index} x={0} y={lines.length === 1 ? 5 : -3 + index * 15}>{line}</tspan>)}</text>
            {here && displayZoom >= 0.9 && <text textAnchor="middle" y={29} className="map-here">You are here</text>}
          </g>}
          {exits.length > 0 && displayZoom >= 0.3 && <g role="img" aria-label={`${exits.join(' and ')} exits`}
            transform={`translate(${ROOM_WIDTH * level.scale / 2 - (exits.length * 17 + 2) / displayZoom}, ${-ROOM_HEIGHT * level.scale / 2 - badgeOffset}) scale(${1 / displayZoom})`} className="map-exit-badges">
            <rect width={exits.length * 17} height={17} rx={2} />
            <text x={exits.length * 8.5} y={13} textAnchor="middle">{up ? '↑' : ''}{down ? '↓' : ''}</text>
          </g>}
        </g>
      })}
    </g>
  }

  return <aside id="map-panel" className="context-panel map-panel" aria-labelledby="map-heading" data-testid="map-panel">
    <div className="map-heading"><h3 id="map-heading">Discovered world</h3>
      <button type="button" onClick={onExpand} aria-expanded={expanded}>{expanded ? 'Collapse map' : 'Expand map'}</button></div>
    {!connected ? <p role="status">Disconnected. Reconnect to refresh your map.</p>
      : !map ? <p role="status">Waiting for map…</p>
        : <>
          <div className="map-controls" role="group" aria-label="Map controls">
            <button type="button" aria-label="Zoom in" disabled={displayZoom >= 3} onClick={() => { manualView(); setZoom(Math.min(3, displayZoom * 1.25)) }}>+</button>
            <button type="button" aria-label="Zoom out" disabled={displayZoom <= 0.1} onClick={() => { manualView(); setZoom(Math.max(0.1, displayZoom / 1.25)) }}>−</button>
            <button type="button" onClick={() => { setFitted(false); setPan({ x: 0, y: 0 }); setZoom(1); setSelected(undefined) }}>Center on me</button>
            <button type="button" aria-pressed={fitted} onClick={() => setFitted(true)}>Fit map</button>
            {!mobile && <button type="button" aria-pressed={nearby} onClick={() => setNearby(value => !value)}>Nearby levels</button>}
            <button type="button" aria-label="Pan north" onClick={() => { manualView(); setPan(p => ({ ...p, y: p.y - 80 / displayZoom })) }}>↑</button>
            <button type="button" aria-label="Pan west" onClick={() => { manualView(); setPan(p => ({ ...p, x: p.x - 80 / displayZoom })) }}>←</button>
            <button type="button" aria-label="Pan east" onClick={() => { manualView(); setPan(p => ({ ...p, x: p.x + 80 / displayZoom })) }}>→</button>
            <button type="button" aria-label="Pan south" onClick={() => { manualView(); setPan(p => ({ ...p, y: p.y + 80 / displayZoom })) }}>↓</button>
          </div>
          <svg ref={viewportRef} className="map-viewport" role="group" aria-label="Discovered rooms and connections"
            viewBox={`${center.x - width / 2} ${center.y - height / 2} ${width} ${height}`}
            onPointerDown={event => {
              if (event.button !== 0 || (event.target as Element).closest('[data-room]')) return
              event.currentTarget.setPointerCapture(event.pointerId)
              manualView()
              drag.current = { x: event.clientX, y: event.clientY, pan: { x: center.x - current.x, y: center.y - current.y } }
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
            {geometry.routes.map(route => <path key={route.key} className="map-stairs" vectorEffect="non-scaling-stroke"
              d={route.points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ')} />)}
            {displayed.filter(level => level.depth !== 0).sort((a, b) => Math.abs(b.depth) - Math.abs(a.depth)).map(renderLevel)}
            {scene[0] && renderLevel(scene[0])}
            {displayed.length > 1 && displayZoom >= 0.4 && displayed.map(level => <text key={level.depth} className="map-level-caption"
              x={level.label.x} y={level.label.y - 12 / displayZoom} textAnchor="middle" style={{ fontSize: 11 / displayZoom }}>
              {level.depth === 0 ? '0 · Current level' : `${level.depth > 0 ? '+' : '−'}${Math.abs(level.depth)} · ${level.depth > 0 ? 'Above' : 'Below'}`}
            </text>)}
          </svg>
          {selectedRoom && <details className="map-details" key={selectedRoom.id} open={selected !== undefined}>
            <summary>{selectedRoom.name} — known exits</summary>
            <ul>{map.exits.filter(edge => edge.room_id === selectedRoom.id).map(edge =>
              <li key={edge.direction}>{edge.direction} → {names.get(edge.destination_room_id)}</li>)}</ul>
          </details>}
          <p className="map-note">{visibleMap.rooms.length} visible {visibleMap.rooms.length === 1 ? 'room' : 'rooms'}. Drag to pan; select rooms for exits.</p>
          <p className="map-legend">Visited rooms only · ↑ Up · ↓ Down{showNearby ? ' · ±2 levels' : ''}</p>
        </>}
  </aside>
}
