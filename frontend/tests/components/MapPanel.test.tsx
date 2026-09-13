import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mapLevels } from '../../src/components/mapLevels'
import MapPanel, { isMapState, layoutMap, MapState } from '../../src/components/MapPanel'

const map: MapState = {
  rooms: [{ id: 'town', name: 'Town Square' }, { id: 'forest', name: 'Forest' }],
  exits: [{ room_id: 'town', direction: 'north', destination_room_id: 'forest' },
    { room_id: 'forest', direction: 'south', destination_room_id: 'town' }],
}
const state = { room_id: 'town', room_name: 'Town Square', inventory: [], map }

describe('Map', () => {
  beforeEach(() => window.localStorage.clear())
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
    fireEvent.click(screen.getByRole('button', { name: 'Nearby levels' }))
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
    expect(isMapState({ rooms: [{ id: 'a', name: 'A', has_up: 'yes' }], exits: [] })).toBe(false)
    expect(isMapState({ rooms: [map.rooms[0], map.rooms[0]], exits: [] })).toBe(false)
    render(<MapPanel state={{ ...state, map: { rooms: null } as unknown as MapState }} connected expanded={false} onExpand={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for map')
  })

  it('limits ghost neighborhoods to two levels each way, without detours to remote level zero', () => {
    const rooms = ['base', 'next', 'up1', 'up2', 'up3', 'down1', 'down2', 'down3', 'remote', 'isolated']
    const floors: MapState = { rooms: rooms.map(id => ({ id, name: id })), exits: [
      { room_id: 'base', direction: 'east', destination_room_id: 'next' },
      { room_id: 'base', direction: 'up', destination_room_id: 'up1' },
      { room_id: 'up1', direction: 'up', destination_room_id: 'up2' },
      { room_id: 'up2', direction: 'up', destination_room_id: 'up3' },
      { room_id: 'up1', direction: 'down', destination_room_id: 'remote' },
      { room_id: 'base', direction: 'down', destination_room_id: 'down1' },
      { room_id: 'down1', direction: 'down', destination_room_id: 'down2' },
      { room_id: 'down2', direction: 'down', destination_room_id: 'down3' },
    ] }
    expect(mapLevels(floors, 'base').map(level => [level.depth, level.map.rooms.map(room => room.id)])).toEqual([
      [0, ['base', 'next']], [1, ['up1']], [-1, ['down1']], [2, ['up2']], [-2, ['down2']],
    ])
    expect(mapLevels(floors, 'up1')[0].map.rooms.map(room => room.id)).toEqual(['up1'])
    expect(mapLevels(floors, 'missing')).toEqual([])
    const view = render(<MapPanel state={{ ...state, room_id: 'base', map: floors }} connected expanded={false} onExpand={() => {}} />)
    expect(view.container.querySelectorAll('[data-level]')).toHaveLength(5)
    expect(within(screen.getByRole('button', { name: 'base, you are here' })).getByRole('img', { name: 'Up and Down exits' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /up3/ })).not.toBeInTheDocument()
    const currentLayout = view.container.querySelector('[data-room="base"]')!.getAttribute('transform')
    fireEvent.click(screen.getByRole('button', { name: 'Nearby levels' }))
    expect(view.container.querySelectorAll('[data-level]')).toHaveLength(1)
    expect(view.container.querySelector('[data-room="base"]')).toHaveAttribute('transform', currentLayout)
    expect(window.localStorage.getItem('mudd-map-nearby')).toBe('false')
  })

  it('keeps labels at screen size and exposes unknown vertical exits without destination names', () => {
    const view = render(<MapPanel state={{ ...state, map: {
      rooms: [{ id: 'town', name: 'Town Square', has_up: true, has_down: true }], exits: [],
    } }} connected expanded={false} onExpand={() => {}} />)
    expect(screen.getByRole('img', { name: 'Up and Down exits' })).toBeInTheDocument()
    expect(view.container.querySelector('.map-label')).toHaveAttribute('transform', 'scale(1)')
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(view.container.querySelector('.map-label')).toHaveAttribute('transform', 'scale(1.25)')
    expect(view.container.querySelectorAll('[data-room]')).toHaveLength(1)
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
