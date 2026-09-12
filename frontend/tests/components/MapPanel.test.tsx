import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MapPanel, { isMapState, layoutMap, MapState } from '../../src/components/MapPanel'

const map: MapState = {
  rooms: [{ id: 'town', name: 'Town Square' }, { id: 'forest', name: 'Forest' }],
  exits: [{ room_id: 'town', direction: 'north', destination_room_id: 'forest' },
    { room_id: 'forest', direction: 'south', destination_room_id: 'town' }],
}
const state = { room_id: 'town', room_name: 'Town Square', inventory: [], map }

describe('Map', () => {
  it('shows current location, inspected connections, zoom/pan/reset, and clears disconnected data', () => {
    const expand = vi.fn()
    const view = render(<MapPanel state={state} connected expanded={false} onExpand={expand} />)
    expect(screen.getByRole('button', { name: 'Town Square, you are here' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Forest' }))
    expect(screen.getByText('south → Town Square')).toBeInTheDocument()
    const svg = screen.getByRole('group', { name: 'Discovered rooms and connections' })
    const original = svg.getAttribute('viewBox')
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(svg.getAttribute('viewBox')).not.toBe(original)
    fireEvent.click(screen.getByRole('button', { name: 'Center on me' }))
    expect(svg.getAttribute('viewBox')).toBe(original)
    fireEvent.click(screen.getByRole('button', { name: 'Pan east' }))
    expect(svg.getAttribute('viewBox')).not.toBe(original)
    fireEvent.click(screen.getByRole('button', { name: 'Expand map' }))
    expect(expand).toHaveBeenCalledOnce()
    view.rerender(<MapPanel state={state} connected={false} expanded={false} onExpand={expand} />)
    expect(screen.getByRole('status')).toHaveTextContent('Disconnected')
    expect(screen.queryByText('Forest')).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Discovered rooms and connections' })).not.toBeInTheDocument()
  })

  it('rejects malformed maps and connections to absent rooms', () => {
    expect(isMapState(map)).toBe(true)
    expect(isMapState({ rooms: map.rooms, exits: [{ room_id: 'town', direction: 'east', destination_room_id: 'secret' }] })).toBe(false)
    expect(isMapState({ rooms: [null], exits: [] })).toBe(false)
    expect(isMapState({ rooms: [map.rooms[0], map.rooms[0]], exits: [] })).toBe(false)
    render(<MapPanel state={{ ...state, map: { rooms: null } as unknown as MapState }} connected expanded={false} onExpand={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for map')
  })

  it('keeps rooms distinct for loops, vertical connections, and disconnected components', () => {
    const complex: MapState = { rooms: ['a', 'b', 'c', 'd', 'e', 'isolated'].map(id => ({ id, name: id })), exits: [
      { room_id: 'a', direction: 'north', destination_room_id: 'b' },
      { room_id: 'b', direction: 'east', destination_room_id: 'c' },
      { room_id: 'a', direction: 'up', destination_room_id: 'd' },
      { room_id: 'd', direction: 'down', destination_room_id: 'a' },
      { room_id: 'c', direction: 'south', destination_room_id: 'e' },
      { room_id: 'e', direction: 'west', destination_room_id: 'a' },
    ] }
    const positions = layoutMap(complex)
    expect(positions.size).toBe(complex.rooms.length)
    expect(new Set([...positions.values()].map(point => `${point.x},${point.y}`)).size).toBe(positions.size)
    expect(layoutMap(complex)).toEqual(positions)
  })
})
