import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Terminal from '../src/components/Terminal'

class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly url: string
  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: (() => void) | null = null
  send = vi.fn()
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED
  })

  constructor(url: string | URL) {
    this.url = url.toString()
    MockWebSocket.instances.push(this)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  receive(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent<string>)
  }
}

describe('Terminal', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    window.localStorage.clear()
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses cookie authentication without putting identity in the URL', () => {
    render(<Terminal username="Alan" />)


    expect(screen.getByText("Alan's Journey")).toBeInTheDocument()
    const socketUrl = new URL(MockWebSocket.instances[0].url)
    expect(socketUrl.search).toBe('')
  })

  it('shows server output and sends commands after connecting', () => {
    render(<Terminal username="Alan" />)

    const socket = MockWebSocket.instances[0]
    act(() => {
      socket.open()
      socket.receive({ type: 'game_output', text: 'Town Square', room_id: 'town_square' })
    })

    expect(screen.getByText(/Online/)).toBeInTheDocument()
    expect(screen.getByText('Town Square')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: 'north' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)

    expect(socket.send).toHaveBeenCalledWith('north')
    expect(screen.getByText('> north')).toBeInTheDocument()
  })

  it('exposes structured command-source metadata without adding transcript text', () => {
    render(<Terminal username="Alan" />)

    act(() => {
      MockWebSocket.instances[0].receive({
        type: 'game_output',
        text: 'You move south.',
        metadata: { command_source: 'ai' },
      })
    })

    expect(screen.getByTestId('terminal')).toHaveAttribute('data-command-source', 'ai')
    expect(screen.getByTestId('transcript')).not.toHaveTextContent('command_source')
  })

  it('applies theme slash commands locally without sending them to the server', () => {
    render(<Terminal username="Alan" />)

    const socket = MockWebSocket.instances[0]
    act(() => socket.open())

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: '/theme light' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)

    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(window.localStorage.getItem('mudd-theme')).toBe('light')
    expect(screen.getByText('Theme changed to light.')).toBeInTheDocument()
    expect(socket.send).not.toHaveBeenCalled()
  })

  it('explains valid options for an invalid theme', () => {
    render(<Terminal username="Alan" />)
    act(() => MockWebSocket.instances[0].open())

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: '/theme sepia' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)

    expect(screen.getByText('Usage: /theme light | dark | techo')).toBeInTheDocument()
    expect(MockWebSocket.instances[0].send).not.toHaveBeenCalled()
  })

  it('toggles safe structured debug output locally', () => {
    render(<Terminal username="Alan" />)
    const socket = MockWebSocket.instances[0]
    act(() => socket.open())

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: '/debug on' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)
    expect(screen.getByText('Debug output enabled.')).toBeInTheDocument()
    expect(screen.getByTestId('terminal')).toHaveAttribute('data-debug', 'on')
    expect(socket.send).not.toHaveBeenCalled()

    act(() => {
      socket.receive({
        type: 'game_output',
        text: 'You move south.',
        success: true,
        room_id: 'docks',
        metadata: { command_source: 'ai' },
      })
    })
    expect(
      screen.getByText(
        '[DEBUG] type=game_output success=true room_id=docks command_source=ai',
      ),
    ).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: '/debug off' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)
    expect(screen.getByText('Debug output disabled.')).toBeInTheDocument()
    expect(screen.getByTestId('terminal')).toHaveAttribute('data-debug', 'off')
  })

  it('shows usage for an invalid debug command', () => {
    render(<Terminal username="Alan" />)
    act(() => MockWebSocket.instances[0].open())

    fireEvent.change(screen.getByTestId('command-input'), { target: { value: '/debug maybe' } })
    fireEvent.submit(screen.getByTestId('command-input').closest('form')!)

    expect(screen.getByText('Usage: /debug on | off')).toBeInTheDocument()
    expect(MockWebSocket.instances[0].send).not.toHaveBeenCalled()
  })

  it('shows server errors in the transcript', () => {
    render(<Terminal username="Alan" />)

    act(() => {
      MockWebSocket.instances[0].receive({ type: 'error', text: 'Username is unavailable.' })
    })

    expect(screen.getByText('[ERROR] Username is unavailable.')).toBeInTheDocument()
  })

  it('closes a socket that finishes connecting after unmount', () => {
    const view = render(<Terminal username="Alan" />)
    const socket = MockWebSocket.instances[0]

    view.unmount()
    socket.open()

    expect(socket.close).toHaveBeenCalledOnce()
  })
})
