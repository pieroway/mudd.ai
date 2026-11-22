import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ClientState } from './InventoryPanel'
import { useFloorTransition } from './useFloorTransition'
import { buildMapScene } from './mapScene'
import { apiUrl } from '../services/api'
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
  const [fullPage, setFullPage] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const openFullPageRef = useRef<HTMLButtonElement>(null)
  const restoreFocus = useRef(false)
  useEffect(() => {
    const dialog = dialogRef.current
    if (fullPage && dialog) {
      dialog.showModal()
      return () => dialog.close()
    }
    if (restoreFocus.current) {
      openFullPageRef.current?.focus()
      restoreFocus.current = false
    }
  }, [fullPage])
  const discoveredMap = isMapState(state?.map) ? state.map : undefined
  const canViewAllLevels = state?.can_view_all_map_levels === true
  const [allLevels, setAllLevels] = useState(false)
  const [allRooms, setAllRooms] = useState(false)
  const [worldMap, setWorldMap] = useState<MapState>()
  const [worldMapError, setWorldMapError] = useState('')
  const requestWorldMap = connected && canViewAllLevels && allRooms
  useEffect(() => {
    if (!canViewAllLevels) {
      setAllLevels(false)
      setAllRooms(false)
    }
  }, [canViewAllLevels])
  useEffect(() => {
    if (!requestWorldMap) {
      setWorldMap(undefined)
      setWorldMapError('')
      return
    }
    const controller = new AbortController()
    setWorldMapError('')
    fetch(apiUrl('/auth/world-map'), { credentials: 'include', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('The all-rooms map is unavailable.')
        const body: unknown = await response.json()
        if (!isMapState(body)) throw new Error('The all-rooms map is unavailable.')
        if (!controller.signal.aborted) setWorldMap(body)
      })
      .catch(() => {
        if (controller.signal.aborted) return
        setWorldMap(undefined)
        setWorldMapError('The all-rooms map is unavailable. Switch the option off and on to retry.')
      })
    return () => controller.abort()
  }, [requestWorldMap, state?.room_id])
  const showAllRooms = requestWorldMap && worldMap !== undefined
  const showAllLevels = canViewAllLevels && (allLevels || showAllRooms)
  const map = showAllRooms ? worldMap : discoveredMap
  const scene = useMemo(() => map ? buildMapScene(map, state?.room_id ?? '', showAllLevels) : [],
    [map, state?.room_id, showAllLevels])
  const positions = scene[0]?.positions ?? new Map<string, Point>()
  const [nearby, setNearby] = useState(() => window.localStorage.getItem('mudd-map-nearby') !== 'false')
  useEffect(() => { window.localStorage.setItem('mudd-map-nearby', String(nearby)) }, [nearby])
  const [mobile, setMobile] = useState(() => window.innerWidth <= 640)
  useEffect(() => {
    const resize = () => setMobile(window.innerWidth <= 640)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  const showNearby = nearby && !mobile && !showAllLevels
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const [fitted, setFitted] = useState(false)
  const [selected, setSelected] = useState<string>()
  const [hovered, setHovered] = useState<string>()
  const [browsedDepth, setBrowsedDepth] = useState(0)
  const roomId = state?.room_id
  useEffect(() => { setBrowsedDepth(0) }, [roomId])
  const viewportRef = useRef<SVGSVGElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
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
  }, [ready, fullPage])
  const drag = useRef<{ x: number; y: number; pan: Point }>()
  const current = positions.get(state?.room_id ?? '') ?? { x: 0, y: 0 }
  const displayed = useMemo(() => scene.filter(level => showAllLevels || showNearby || level.depth === 0),
    [scene, showAllLevels, showNearby])
  const activeLevel = displayed.find(level => level.depth === browsedDepth) ?? displayed[0]
  const activeDepth = activeLevel?.depth ?? 0
  useEffect(() => { if (activeDepth === 0) setBrowsedDepth(0) }, [activeDepth])
  let focusPoint = current
  let focusRoom = roomId
  if (activeDepth !== 0 && activeLevel) {
    let bestDistance = Infinity
    for (const [id, point] of activeLevel.positions) {
      const distance = Math.hypot(point.x - current.x, point.y - current.y)
      if (distance >= bestDistance) continue
      focusPoint = point
      focusRoom = id
      bestDistance = distance
    }
  }
  const displayedRooms = displayed.flatMap(level => level.map.rooms)
  const selectedRoom = displayedRooms.find(room => room.id === selected)
    ?? displayedRooms.find(room => room.id === focusRoom)
  const names = new Map(map?.rooms.map(room => [room.id, room.name]))
  const allPositions = new Map(displayed.flatMap(level => [...level.positions]))
  const depths = new Map(displayed.flatMap(level => level.map.rooms.map(room => [room.id, level.depth] as const)))
  const geometry = useMemo(() => {
    const points = displayed.flatMap(level => [...level.positions.values()].flatMap(point => [
      { x: point.x - ROOM_WIDTH / 2, y: point.y - ROOM_HEIGHT / 2 },
      { x: point.x + ROOM_WIDTH / 2, y: point.y + ROOM_HEIGHT / 2 },
    ]))
    return {
      left: Math.min(0, ...points.map(p => p.x)), right: Math.max(0, ...points.map(p => p.x)),
      top: Math.min(0, ...points.map(p => p.y)), bottom: Math.max(0, ...points.map(p => p.y)),
    }
  }, [displayed])
  const fitZoom = Math.min(1, (viewport.width - Math.min(96, viewport.width * 0.25)) / Math.max(1, geometry.right - geometry.left),
    (viewport.height - Math.min(96, viewport.height * 0.25)) / Math.max(1, geometry.bottom - geometry.top))
  const displayZoom = fitted ? fitZoom : zoom
  const width = viewport.width / displayZoom
  const height = viewport.height / displayZoom
  const center = fitted ? { x: (geometry.left + geometry.right) / 2, y: (geometry.top + geometry.bottom) / 2 }
    : { x: focusPoint.x + pan.x, y: focusPoint.y + pan.y }
  const manualView = useCallback(() => {
    setFitted(false)
    setZoom(displayZoom)
    setPan({ x: center.x - focusPoint.x, y: center.y - focusPoint.y })
  }, [displayZoom, center.x, center.y, focusPoint.x, focusPoint.y])
  const zoomBy = useCallback((factor: number) => {
    if (factor > 1 ? displayZoom >= 3 : displayZoom <= 0.1) return
    manualView()
    setZoom(Math.max(0.1, Math.min(3, displayZoom * factor)))
  }, [displayZoom, manualView])
  const viewFloor = useCallback((depth: number) => {
    setBrowsedDepth(depth)
    setPan({ x: 0, y: 0 })
    setSelected(undefined)
  }, [])
  useEffect(() => {
    const canvas = canvasRef.current
    if (!ready || !canvas) return
    const wheel = (event: WheelEvent) => {
      if (!event.deltaY) return
      event.preventDefault()
      const up = event.deltaY < 0
      if (!event.ctrlKey) {
        zoomBy(up ? 1.25 : 1 / 1.25)
        return
      }
      const depths = displayed.map(level => level.depth).sort((a, b) => a - b)
      const next = depths[depths.indexOf(activeDepth) + (up ? 1 : -1)]
      if (next !== undefined) viewFloor(next)
    }
    canvas.addEventListener('wheel', wheel, { passive: false })
    return () => canvas.removeEventListener('wheel', wheel)
  }, [ready, fullPage, displayed, activeDepth, zoomBy, viewFloor])
  const priority = (id: string) => id === hovered || id === selected ? 0 : id === state?.room_id ? 1 : 2
  const labelWidthFor = (id: string) => ROOM_WIDTH - (depths.get(id) === activeDepth ? 16 : 34)
  const labelOffset = (depth: number) => depth ? -Math.sign(depth) * ROOM_HEIGHT * 3 / 8 : 0
  const labelBoxes: { x: number; y: number; width: number; height: number }[] = []
  const labels = new Set<string>()
  // Current labels take precedence, then the exposed strips of nearby floors.
  for (const room of [...displayedRooms].sort((a, b) =>
    Math.abs((depths.get(a.id) ?? 0) - activeDepth) - Math.abs((depths.get(b.id) ?? 0) - activeDepth)
      || priority(a.id) - priority(b.id))) {
    const point = allPositions.get(room.id)!
    const depth = (depths.get(room.id) ?? 0) - activeDepth
    if (displayZoom < 0.2 || (depth ? displayZoom < 0.8 : priority(room.id) === 2 && displayZoom < 0.45)) continue
    const box = { x: point.x * displayZoom, y: (point.y + labelOffset(depth)) * displayZoom,
      width: labelWidthFor(room.id) * displayZoom, height: (depth ? 14 : 34) * displayZoom }
    if (labelBoxes.some(other => Math.abs(other.x - box.x) < (other.width + box.width) / 2 + 4
      && Math.abs(other.y - box.y) < (other.height + box.height) / 2)) continue
    labels.add(room.id)
    labelBoxes.push(box)
  }

  const renderLevel = (level: typeof scene[number]) => {
    const drawn = new Set<string>()
    const relativeDepth = level.depth - activeDepth
    const ghost = relativeDepth !== 0
    return <g key={level.depth} data-level={level.depth} data-distance={Math.abs(relativeDepth)}
      className={ghost ? 'map-ghost-layer' : 'map-main-layer'}>
      {level.map.exits.map(edge => {
        const key = [edge.room_id, edge.destination_room_id].sort().join(':')
        if (drawn.has(key)) return null
        drawn.add(key)
        const from = level.positions.get(edge.room_id)!
        const to = level.positions.get(edge.destination_room_id)!
        return <path key={key} d={`M ${from.x} ${from.y} H ${(from.x + to.x) / 2} V ${to.y} H ${to.x}`}
          className="map-edge" fill="none" />
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
          aria-label={`${room.name}${here ? ', you are here' : ''}${level.depth ? `, level ${level.depth > 0 ? '+' : ''}${level.depth}` : ''}`}
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
            width={ROOM_WIDTH} height={ROOM_HEIGHT} rx={5} />
          {labels.has(room.id) && <g className="map-label" transform={ghost
            ? `translate(0, ${labelOffset(relativeDepth)})` : undefined}>
            <rect className="map-label-background" x={-labelWidth / 2} y={ghost ? -7 : -17} width={labelWidth} height={ghost ? 14 : 34} rx={3} />
            <text textAnchor="middle">{lines.map((line, index) =>
              <tspan key={index} x={0} y={(lines.length === 1 ? 5 : -3 + index * 15) - (here ? 7 : 0)}>{line}</tspan>)}</text>
            {here && !ghost && displayZoom >= 0.6 && <g className="map-here" transform="translate(0, 26)">
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

  const panel = <aside id="map-panel" className="context-panel map-panel"
    aria-labelledby="map-heading" data-testid="map-panel">
    <div className="map-heading"><h3 id="map-heading">Discovered world</h3>
      <div className="map-size-controls" role="group" aria-label="Map size">
        {fullPage ? <button type="button" title="Exit full-page map" aria-label="Exit full-page map"
          onClick={() => setFullPage(false)}><span aria-hidden="true">❐</span></button> : <>
          <button type="button" onClick={onExpand} aria-expanded={expanded}
            title={expanded ? 'Collapse map' : 'Expand map'} aria-label={expanded ? 'Collapse map' : 'Expand map'}>
            <span aria-hidden="true">{expanded ? '⇥⇤' : '⇤⇥'}</span>
          </button>
          <button type="button" ref={openFullPageRef} title="Maximize map" aria-label="Maximize map"
            onClick={() => { restoreFocus.current = true; setFullPage(true) }}>
            <span aria-hidden="true">⛶</span>
          </button>
        </>}
      </div>
    </div>
    {!connected ? <p role="status">Disconnected. Reconnect to refresh your map.</p>
      : !map ? <p role="status">Waiting for map…</p>
        : <>
          <div className="map-controls" role="group" aria-label="Map controls">
            <button type="button" aria-label="Zoom in" disabled={displayZoom >= 3} onClick={() => zoomBy(1.25)}>+</button>
            <button type="button" aria-label="Zoom out" disabled={displayZoom <= 0.1} onClick={() => zoomBy(1 / 1.25)}>−</button>
            <button type="button" onClick={() => { viewFloor(0); setFitted(false); setZoom(1) }}>Center on me</button>
            <button type="button" aria-pressed={fitted} onClick={() => setFitted(true)}>Fit map</button>
            {!mobile && <button type="button" aria-label="Nearby levels" aria-pressed={showNearby} onClick={() => {
              setNearby(!showNearby)
              setAllLevels(false)
              setAllRooms(false)
            }}>Nearby levels <span className="map-toggle-dot" aria-hidden="true">{showNearby ? '●' : '○'}</span></button>}
            {canViewAllLevels && <>
              <button type="button" aria-pressed={allLevels && !requestWorldMap}
                onClick={() => { setAllLevels(!allLevels || requestWorldMap); setAllRooms(false) }}>All levels <span className="map-toggle-dot" aria-hidden="true">{allLevels && !requestWorldMap ? '●' : '○'}</span></button>
              <button type="button" aria-pressed={requestWorldMap}
                onClick={() => setAllRooms(value => !value)}>All levels · All rooms <span className="map-toggle-dot" aria-hidden="true">{requestWorldMap ? '●' : '○'}</span></button>
            </>}
          </div>
          {requestWorldMap && (worldMapError ? <p role="alert">{worldMapError}</p>
            : !worldMap && <p role="status">Loading all rooms…</p>)}
          <div className="map-canvas" ref={canvasRef}>
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
                drag.current = { x: event.clientX, y: event.clientY, pan: { x: center.x - focusPoint.x, y: center.y - focusPoint.y } }
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
              {[...displayed].sort((a, b) => Math.abs(b.depth - activeDepth) - Math.abs(a.depth - activeDepth)).map(renderLevel)}

            </svg>
            {activeDepth !== 0 && <div className="map-level-indicator">
              <span role="status">Viewing level {activeDepth > 0 ? '+' : ''}{activeDepth}</span>
              <button type="button" aria-label="Reset to my level" title="Reset to my level"
                onClick={() => viewFloor(0)}><span aria-hidden="true">↺</span></button>
            </div>}
          </div>
          {selectedRoom && <details className="map-details" key={selectedRoom.id} open={selected !== undefined}>
            <summary>{selectedRoom.name} — {showAllRooms ? 'mapped exits' : 'known exits'}</summary>
            <ul>{map.exits.filter(edge => edge.room_id === selectedRoom.id
              && (!showAllRooms || allPositions.has(edge.destination_room_id))).map(edge =>
              <li key={edge.direction}>{edge.direction} → {names.get(edge.destination_room_id)}</li>)}</ul>
          </details>}
          <p className="map-note">{activeLevel?.map.rooms.length ?? 0} visible {activeLevel?.map.rooms.length === 1 ? 'room' : 'rooms'}. Drag to pan; select rooms for exits.</p>
          <p className="map-legend">{showAllRooms ? 'Visited and unvisited rooms' : 'Visited rooms only'} · ↑ Up · ↓ Down{showAllLevels
            ? ' · All levels within 10 rooms' : showNearby ? ' · ↖ Above · ↘ Below · ±2 levels' : ''}</p>
        </>}
  </aside>
  return fullPage ? <dialog className="map-full-page" ref={dialogRef} aria-labelledby="map-heading"
    onCancel={event => { event.preventDefault(); setFullPage(false) }}>{panel}</dialog> : panel
}
