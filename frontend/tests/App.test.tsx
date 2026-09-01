import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../src/App'

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

describe('App', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('enters the world with the submitted username', () => {
    render(<App />)

    fireEvent.change(screen.getByTestId('username-input'), { target: { value: 'Alan Smith' } })
    fireEvent.click(screen.getByTestId('login-button'))

    expect(screen.getByText("Alan Smith's Journey")).toBeInTheDocument()
    const socketUrl = new URL(MockWebSocket.instances[0].url)
    expect(socketUrl.searchParams.get('username')).toBe('Alan Smith')
  })

  it('shows server output and sends commands after connecting', () => {
    render(<App />)
    fireEvent.change(screen.getByTestId('username-input'), { target: { value: 'Alan' } })
    fireEvent.click(screen.getByTestId('login-button'))

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
})
