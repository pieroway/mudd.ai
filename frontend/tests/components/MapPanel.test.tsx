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
  it('maps only the current horizontal neighborhood and switches views when changing levels', () => {
    const neighborhood: MapState = {
      rooms: [
        { id: 'street', name: 'Street' },
        { id: 'hall', name: 'Hall', building_id: 'house' },
        { id: 'landing', name: 'Landing', building_id: 'house' },
        { id: 'bedroom', name: 'Bedroom', building_id: 'house' },
        { id: 'remote', name: 'Remote Street' },
        { id: 'cellar', name: 'Cellar', building_id: 'house' },
        { id: 'isolated', name: 'Isolated' },
      ],
      exits: [
        { room_id: 'bedroom', direction: 'west', destination_room_id: 'landing' },
        { room_id: 'bedroom', direction: 'down', destination_room_id: 'remote' },
        { room_id: 'hall', direction: 'up', destination_room_id: 'landing' },
        { room_id: 'landing', direction: 'down', destination_room_id: 'hall' },
        { room_id: 'hall', direction: 'down', destination_room_id: 'cellar' },
        { room_id: 'street', direction: 'east', destination_room_id: 'hall' },
      ],
    }
    const renderRoom = (id: string) => <MapPanel state={{ ...state, room_id: id, map: neighborhood }} connected expanded={false} onExpand={() => {}} />
    const view = render(renderRoom('street'))
    const visibleIds = () => [...view.container.querySelectorAll('[data-room]')].map(room => room.getAttribute('data-room'))
    expect(visibleIds()).toEqual(['street', 'hall'])
    fireEvent.click(screen.getByRole('button', { name: 'Hall' }))
    expect(screen.getByText('up → Landing')).toBeInTheDocument()

    view.rerender(renderRoom('landing'))
    expect(visibleIds()).toEqual(['landing', 'bedroom'])
    expect(screen.getByText('Landing — known exits')).toBeInTheDocument()
    expect(screen.queryByText('Hall — known exits')).not.toBeInTheDocument()
    expect(view.container.querySelectorAll('.map-edge')).toHaveLength(1)

    view.rerender(renderRoom('remote'))
    expect(visibleIds()).toEqual(['remote'])
    expect(screen.getByText(/1 visible room\./)).toBeInTheDocument()
    view.rerender(renderRoom('cellar'))
    expect(visibleIds()).toEqual(['cellar'])
    view.rerender(renderRoom('street'))
    expect(visibleIds()).toEqual(['street', 'hall'])
  })

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
