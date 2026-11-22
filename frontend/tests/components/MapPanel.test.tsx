import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
  afterEach(() => vi.unstubAllGlobals())
  it('loads unvisited rooms only in the privileged all-rooms view', async () => {
    const world = { rooms: [...map.rooms, { id: 'loft', name: 'Loft' }],
      exits: [...map.exits, { room_id: 'town', direction: 'up', destination_room_id: 'loft' }] }
    const fetchMap = vi.fn().mockResolvedValue({ ok: true, json: async () => world })
    vi.stubGlobal('fetch', fetchMap)
    const panel = (allowed: boolean) => <MapPanel state={{
      ...state, can_view_all_map_levels: allowed,
    }} connected expanded={false} onExpand={() => {}} />
    const view = render(panel(false))
    const button = { name: 'All levels · All rooms' }
    expect(screen.queryByRole('button', button)).toBeNull()
    expect(fetchMap).not.toHaveBeenCalled()
    view.rerender(panel(true))
    fireEvent.click(screen.getByRole('button', button))
    expect(await screen.findByRole('button', { name: 'Loft, level +1' })).toBeInTheDocument()
    expect(fetchMap).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/auth/world-map' }),
      expect.objectContaining({ credentials: 'include' }))
    view.rerender(panel(false))
    expect(screen.queryByRole('button', { name: 'Loft, level +1' })).toBeNull()
  })
  it('gates All levels and measures its radius from the player across distant floors', () => {
    const tower: MapState = {
      rooms: Array.from({ length: 7 }, (_, i) => ({ id: `floor-${i}`, name: `Floor ${i}` })),
      exits: Array.from({ length: 6 }, (_, i) => ({
        room_id: `floor-${i}`, direction: 'up', destination_room_id: `floor-${i + 1}`,
      })),
    }
    for (let i = 1; i <= 11; i += 1) {
      tower.rooms.push({ id: `wing-${i}`, name: `Wing ${i}` })
      tower.exits.push({ room_id: i === 1 ? 'floor-6' : `wing-${i - 1}`,
        direction: 'east', destination_room_id: `wing-${i}` })
    }
    const panel = (allowed: boolean) => <MapPanel state={{
      ...state, room_id: 'floor-0', map: tower, can_view_all_map_levels: allowed,
    }} connected expanded={false} onExpand={() => {}} />
    const view = render(panel(false))
    expect(screen.queryByRole('button', { name: 'All levels' })).toBeNull()
    view.rerender(panel(true))
    const toggle = screen.getByRole('button', { name: 'All levels' })
    expect(screen.queryByRole('button', { name: 'Floor 6, level +6' })).toBeNull()
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Floor 6, level +6' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Wing 10, level +6' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Wing 11, level +6' })).toBeNull()
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Nearby levels' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('button', { name: 'Floor 6, level +6' })).toBeNull()
  })
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
    fireEvent.keyDown(svg, { key: 'ArrowRight' })
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

  it('scales labels with the map and exposes unknown vertical exits without destination names', () => {
    const view = render(<MapPanel state={{ ...state, map: {
      rooms: [{ id: 'town', name: 'Town Square', has_up: true, has_down: true }], exits: [],
    } }} connected expanded={false} onExpand={() => {}} />)
    expect(screen.getByRole('img', { name: 'Up and Down exits' })).toBeInTheDocument()
    expect(view.container.querySelectorAll('.map-exit-badges rect')).toHaveLength(0)
    expect(screen.getByText('YOU')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Pan / })).not.toBeInTheDocument()
    const label = view.container.querySelector('.map-label')
    expect(label).not.toHaveAttribute('transform')
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(label).not.toHaveAttribute('transform')
    expect(view.container.querySelectorAll('[data-room]')).toHaveLength(1)
  })

  it('fits every displayed floor and returns to manual controls without moving rooms', () => {
    const floors: MapState = { rooms: ['town', 'upper', 'lower', 'far'].map(id => ({ id, name: id })), exits: [
      { room_id: 'town', direction: 'up', destination_room_id: 'upper' },
      { room_id: 'upper', direction: 'east', destination_room_id: 'far' },
      { room_id: 'town', direction: 'down', destination_room_id: 'lower' },
    ] }
    const view = render(<MapPanel state={{ ...state, map: floors }} connected expanded onExpand={() => {}} />)
    const svg = screen.getByRole('group', { name: 'Discovered rooms and connections' })
    const initial = svg.getAttribute('viewBox')
    const fit = screen.getByRole('button', { name: 'Fit map' })
    fireEvent.click(fit)
    expect(fit).toHaveAttribute('aria-pressed', 'true')
    const [x, y, width, height] = svg.getAttribute('viewBox')!.split(' ').map(Number)
    for (const room of view.container.querySelectorAll('[data-room]')) {
      const [px, py] = room.getAttribute('transform')!.match(/-?\d+(?:\.\d+)?/g)!.map(Number)
      expect(px - 88).toBeGreaterThanOrEqual(x)
      expect(px + 88).toBeLessThanOrEqual(x + width)
      expect(py - 40).toBeGreaterThanOrEqual(y)
      expect(py + 40).toBeLessThanOrEqual(y + height)
    }
    const allFloors = svg.getAttribute('viewBox')
    fireEvent.click(screen.getByRole('button', { name: 'Nearby levels' }))
    expect(svg.getAttribute('viewBox')).not.toBe(allFloors)
    fireEvent.keyDown(svg, { key: 'ArrowRight' })
    expect(fit).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Center on me' }))
    expect(svg.getAttribute('viewBox')).toBe(initial)
  })

  it('draws same-size ghost boxes behind the current floor with labels in exposed strips and split badges', () => {
    const floors: MapState = { rooms: ['town', 'upper', 'lower', 'attic'].map(id => ({ id, name: id })), exits: [
      { room_id: 'town', direction: 'up', destination_room_id: 'upper' },
      { room_id: 'town', direction: 'down', destination_room_id: 'lower' },
      { room_id: 'upper', direction: 'up', destination_room_id: 'attic' },
    ] }
    const view = render(<MapPanel state={{ ...state, map: floors }} connected expanded onExpand={() => {}} />)
    const layers = [...view.container.querySelectorAll('[data-level]')]
    expect(layers[layers.length - 1]).toHaveAttribute('data-level', '0')
    const current = view.container.querySelector('[data-room="town"]')!
    for (const box of view.container.querySelectorAll('.map-room-box')) {
      expect(box).toHaveAttribute('width', '176')
      expect(box).toHaveAttribute('height', '80')
    }
    expect(view.container.querySelector('[data-room="upper"] .map-label')).toHaveAttribute('transform', 'translate(0, -30)')
    expect(view.container.querySelector('[data-room="lower"] .map-label')).toHaveAttribute('transform', 'translate(0, 30)')
    const badgeY = (direction: string) => Number(current.querySelector(`[data-exit="${direction}"]`)!
      .getAttribute('transform')!.match(/translate\([^,]+, ([^)]+)\)/)![1])
    expect(badgeY('up')).toBeLessThan(0)
    expect(badgeY('down')).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'upper, level +1' }))
    expect(screen.getByText('upper — known exits')).toBeInTheDocument()
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
