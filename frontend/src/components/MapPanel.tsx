import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClientState } from './InventoryPanel'
import { useFloorTransition } from './useFloorTransition'
import { buildMapScene } from './mapScene'
export { layoutMap } from './mapScene'
import { ROOM_HEIGHT, ROOM_WIDTH, roomNameLines, type Point } from './mapGeometry'

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

export default function MapPanel({ state, connected, expanded, onExpand }: {
  state?: ClientState; connected: boolean; expanded: boolean; onExpand: () => void
}) {
  const map = isMapState(state?.map) ? state.map : undefined
  const scene = useMemo(() => map ? buildMapScene(map, state?.room_id ?? '') : [], [map, state?.room_id])
  const visibleMap = scene[0]?.map ?? { rooms: [], exits: [] }
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
  useFloorTransition(viewportRef, ready ? state?.room_id : undefined, map)
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
    const points = shown.flatMap(level => [...level.positions.values()].flatMap(point => [
      { x: point.x - ROOM_WIDTH / 2, y: point.y - ROOM_HEIGHT / 2 },
      { x: point.x + ROOM_WIDTH / 2, y: point.y + ROOM_HEIGHT / 2 },
    ]))
    return {
      left: Math.min(0, ...points.map(p => p.x)), right: Math.max(0, ...points.map(p => p.x)),
      top: Math.min(0, ...points.map(p => p.y)), bottom: Math.max(0, ...points.map(p => p.y)),
    }
  }, [scene, showNearby])
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
  const labelWidthFor = (id: string) => Math.max(48, Math.min(160,
    ROOM_WIDTH * displayZoom - (depths.get(id) ? 34 : 12)))
  const labelOffset = (depth: number) => depth ? -Math.sign(depth) * ROOM_HEIGHT * 3 / 8 : 0
  const labelBoxes: { x: number; y: number; width: number; height: number }[] = []
  const labels = new Set<string>()
  // Current labels take precedence, then the exposed strips of nearby floors.
  for (const room of [...displayedRooms].sort((a, b) =>
    Math.abs(depths.get(a.id) ?? 0) - Math.abs(depths.get(b.id) ?? 0) || priority(a.id) - priority(b.id))) {
    const point = allPositions.get(room.id)!
    const depth = depths.get(room.id) ?? 0
    if (displayZoom < 0.2 || (depth ? displayZoom < 0.8 : priority(room.id) === 2 && displayZoom < 0.45)) continue
    const box = { x: point.x * displayZoom, y: (point.y + labelOffset(depth)) * displayZoom,
      width: labelWidthFor(room.id), height: depth ? 14 : 34 }
    if (labelBoxes.some(other => Math.abs(other.x - box.x) < (other.width + box.width) / 2 + 4
      && Math.abs(other.y - box.y) < (other.height + box.height) / 2)) continue
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
        const labelWidth = labelWidthFor(room.id)
        const characters = Math.max(3, Math.floor(labelWidth / 7.2))
        const lines = ghost ? [room.name.length > characters ? `${room.name.slice(0, characters - 1)}…` : room.name]
          : roomNameLines(room.name, characters)
        const badgeSize = Math.min(17, ROOM_HEIGHT * displayZoom / 4 - 2)
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
          <rect className="map-room-box" x={-ROOM_WIDTH / 2} y={-ROOM_HEIGHT / 2}
            width={ROOM_WIDTH} height={ROOM_HEIGHT} rx={5} vectorEffect="non-scaling-stroke" />
          {labels.has(room.id) && <g className="map-label" transform={ghost
            ? `translate(0, ${labelOffset(level.depth)}) scale(${1 / displayZoom})` : `scale(${1 / displayZoom})`}>
            <rect className="map-label-background" x={-labelWidth / 2} y={ghost ? -7 : -17} width={labelWidth} height={ghost ? 14 : 34} rx={3} />
            <text textAnchor="middle">{lines.map((line, index) =>
              <tspan key={index} x={0} y={(lines.length === 1 ? 5 : -3 + index * 15) - (here ? 7 : 0)}>{line}</tspan>)}</text>
            {here && displayZoom >= 0.6 && <g className="map-here" transform={`translate(0, ${26 * Math.min(1, displayZoom)}) scale(${Math.min(1, displayZoom)})`}>
              <rect x={-20} y={-9} width={40} height={19} rx={3} />
              <text textAnchor="middle" y={5}>YOU</text>
            </g>}
          </g>}
          {exits.length > 0 && displayZoom >= 0.3 && <g role="img" aria-label={`${exits.join(' and ')} exits`}>
            {([['up', up, '↑'], ['down', down, '↓']] as const).filter(([, enabled]) => enabled).map(([direction, , symbol]) =>
              <g key={direction} data-exit={direction} className="map-exit-badges"
                transform={`translate(${ROOM_WIDTH / 2 - (badgeSize + 2) / displayZoom}, ${direction === 'up'
                  ? -ROOM_HEIGHT / 2 + 2 / displayZoom : ROOM_HEIGHT / 2 - (badgeSize + 2) / displayZoom}) scale(${badgeSize / 17 / displayZoom})`}>
                <text x={8.5} y={13} textAnchor="middle">{symbol}</text>
              </g>)}
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
            {!mobile && <button type="button" aria-label="Nearby levels" aria-pressed={nearby} onClick={() => setNearby(value => !value)}>Nearby levels <span className="map-toggle-dot" aria-hidden="true">{nearby ? '●' : '○'}</span></button>}
          </div>
          <svg ref={viewportRef} className="map-viewport" role="group" tabIndex={0}
            onKeyDown={event => {
              if (event.target !== event.currentTarget) return
              const delta: Record<string, Point> = { ArrowUp: { x: 0, y: -80 }, ArrowDown: { x: 0, y: 80 },
                ArrowLeft: { x: -80, y: 0 }, ArrowRight: { x: 80, y: 0 } }
              const move = delta[event.key]
              if (!move) return
              event.preventDefault(); manualView()
              setPan(p => ({ x: p.x + move.x / displayZoom, y: p.y + move.y / displayZoom }))
            }} aria-label="Discovered rooms and connections"
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
            {displayed.filter(level => level.depth !== 0).sort((a, b) => Math.abs(b.depth) - Math.abs(a.depth)).map(renderLevel)}
            {scene[0] && renderLevel(scene[0])}

          </svg>
          {selectedRoom && <details className="map-details" key={selectedRoom.id} open={selected !== undefined}>
            <summary>{selectedRoom.name} — known exits</summary>
            <ul>{map.exits.filter(edge => edge.room_id === selectedRoom.id).map(edge =>
              <li key={edge.direction}>{edge.direction} → {names.get(edge.destination_room_id)}</li>)}</ul>
          </details>}
          <p className="map-note">{visibleMap.rooms.length} visible {visibleMap.rooms.length === 1 ? 'room' : 'rooms'}. Drag to pan; select rooms for exits.</p>
          <p className="map-legend">Visited rooms only · ↑ Up · ↓ Down{showNearby ? ' · ↖ Above · ↘ Below · ±2 levels' : ''}</p>
        </>}
  </aside>
}
