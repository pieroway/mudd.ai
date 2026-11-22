import { useEffect, useState } from 'react'
import { apiUrl } from '../services/api'

interface MazeRoom {
  id: string; name: string; x: number; y: number; z: number; carts: number
}

interface MazeExit {
  room_id: string; destination_room_id: string; direction: string
  rail: boolean; door: string | null; hidden: boolean; locked: boolean; jammed: boolean; open: boolean
}

interface MazeMap {
  current_room_id: string; rooms: MazeRoom[]; exits: MazeExit[]
}

export default function MazeMapPanel({ roomId, onBack }: { roomId?: string; onBack: () => void }) {
  const [map, setMap] = useState<MazeMap>()
  const [error, setError] = useState('')
  const [depth, setDepth] = useState('all')
  const [selection, setSelection] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    fetch(apiUrl('/auth/maze-map'), { credentials: 'include', signal: controller.signal })
      .then(async response => {
        const body = await response.json()
        if (!response.ok) throw new Error(body.detail ?? 'Maze map unavailable.')
        if (!controller.signal.aborted) { setError(''); setMap(body) }
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) {
          setMap(undefined)
          setError(failure instanceof Error ? failure.message : 'Maze map unavailable.')
        }
      })
    return () => controller.abort()
  }, [roomId, revision])

  const rooms = map?.rooms ?? []
  const byId = new Map(rooms.map(room => [room.id, room]))
  const depths = [...new Set(rooms.map(room => room.z))].sort((a, b) => b - a)
  const shown = depths.filter(z => depth === 'all' || String(z) === depth)
  const floors = shown.length ? shown : depths
  const visible = rooms.filter(room => floors.includes(room.z))
  const selected = visible.find(room => room.id === selection)
    ?? visible.find(room => room.id === map?.current_room_id) ?? visible[0]
  return <aside className="context-panel map-panel" aria-labelledby="maze-map-heading" data-testid="map-panel">
    <div className="map-heading"><h3 id="maze-map-heading">Maze admin map</h3>
      <button type="button" onClick={onBack}>Discovered map</button>
      <button type="button" onClick={() => { setMap(undefined); setError(''); setRevision(value => value + 1) }}>Refresh</button>
    </div>
    {error ? <p role="alert">{error}</p> : !map ? <p role="status">Loading maze map…</p> : <>
      <label>Depth <select value={shown.length ? depth : 'all'} onChange={event => setDepth(event.target.value)}>
        <option value="all">All levels</option>
        {depths.map(z => <option key={z} value={z}>Level {z}</option>)}
      </select></label>
      <div className="maze-map-levels">
        {floors.map(z => {
          const floor = visible.filter(room => room.z === z)
          const ids = new Set(floor.map(room => room.id))
          const edges = map.exits.filter(edge => ids.has(edge.room_id) && ids.has(edge.destination_room_id)
            && edge.room_id < edge.destination_room_id)
          const left = Math.min(...floor.map(room => room.x))
          const top = Math.min(...floor.map(room => room.y))
          const width = Math.max(...floor.map(room => room.x)) - left + 1
          const height = Math.max(...floor.map(room => room.y)) - top + 1
          return <section key={z} aria-label={`Level ${z}`}>
            <h4>Level {z}</h4>
            <svg viewBox={`${left * 38 - 19} ${top * 38 - 19} ${width * 38} ${height * 38}`} aria-hidden="true">
              {edges.map(edge => {
                const from = byId.get(edge.room_id)!
                const to = byId.get(edge.destination_room_id)!
                return <line key={`${from.id}-${to.id}`} x1={from.x * 38} y1={from.y * 38}
                  x2={to.x * 38} y2={to.y * 38} stroke={edge.rail ? 'var(--accent-color)' : 'currentColor'}
                  strokeWidth={edge.rail ? 4 : 2} strokeDasharray={edge.hidden ? '3 3' : undefined} />
              })}
              {floor.map(room => <g key={room.id} transform={`translate(${room.x * 38} ${room.y * 38})`}
                onClick={() => setSelection(room.id)} className="maze-map-room">
                <title>{room.name}</title>
                <rect x={-11} y={-9} width={22} height={18} rx={3}
                  fill={selected?.id === room.id ? 'var(--accent-color)' : 'var(--bg-light)'} stroke="currentColor" />
                {(room.carts > 0 || room.id === map.current_room_id) && <text textAnchor="middle" y={3}>
                  {room.carts > 0 ? 'C' : '●'}
                </text>}
              </g>)}
            </svg>
          </section>
        })}
      </div>
      {selected && <div className="maze-map-detail">
        <label>Room <select value={selected.id} onChange={event => setSelection(event.target.value)}>
          {visible.map(room => <option key={room.id} value={room.id}>{room.name} ({room.x}, {room.y}, {room.z})</option>)}
        </select></label>
        <p>Coordinates ({selected.x}, {selected.y}, {selected.z}) · Minecarts {selected.carts}</p>
        <ul>{map.exits.filter(edge => edge.room_id === selected.id).map(edge => <li key={edge.direction}>
          {edge.direction} → {byId.get(edge.destination_room_id)?.name ?? 'Outside this maze'}
          {edge.rail && ' · rail'}{edge.door && ` · ${edge.door} (${edge.open ? 'open' : 'closed'})`}
          {edge.hidden && ' · concealed'}{edge.locked && ' · locked'}{edge.jammed && ' · jammed'}
        </li>)}</ul>
      </div>}
    </>}
  </aside>
}
