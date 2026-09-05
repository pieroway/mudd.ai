import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'

vi.mock('../src/components/Terminal', () => ({ default: ({ username }: { username: string }) => <div>Character: {username}</div> }))

describe('Account login', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: 'Please sign in.' }) })
  })
  afterEach(() => vi.unstubAllGlobals())

  async function fillCredentials() {
    fireEvent.change(await screen.findByTestId('username-input'), { target: { value: 'Alice' } })
    fireEvent.change(screen.getByTestId('password-input'), { target: { value: 'A long test-only passphrase1!' } })
  }

  it('waits for authenticated server identity before entering the world', async () => {
    render(<App />)
    await fillCredentials()
    expect(screen.queryByText('Character: Alice')).not.toBeInTheDocument()
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ username: 'Alice' }) })
    fireEvent.click(screen.getByTestId('login-button'))
    expect(await screen.findByText('Character: Alice')).toBeInTheDocument()
    expect(fetchMock.mock.calls[1][1].credentials).toBe('include')
    expect(window.localStorage.getItem('password')).toBeNull()
  })

  it('keeps login visible and clears the password on rejection', async () => {
    render(<App />)
    await fillCredentials()
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({ detail: 'Invalid username or password.' }) })
    fireEvent.click(screen.getByTestId('login-button'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(screen.getByTestId('password-input')).toHaveValue('')
  })

  it('registers explicitly then revokes the session on logout', async () => {
    render(<App />)
    fireEvent.click(await screen.findByTestId('register-toggle'))
    await fillCredentials()
    fetchMock.mockResolvedValueOnce({ ok: true, status: 201, json: async () => ({ username: 'Alice' }) })
    fireEvent.click(screen.getByTestId('login-button'))
    await screen.findByText('Character: Alice')
    expect(fetchMock.mock.calls[1][0].pathname).toBe('/auth/register')
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204 })
    fireEvent.click(screen.getByTestId('logout-button'))
    await waitFor(() => expect(screen.queryByText('Character: Alice')).not.toBeInTheDocument())
    expect(fetchMock.mock.calls[2][0].pathname).toBe('/auth/logout')
  })

  it('restores an existing session after page reload', async () => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ username: 'Alice' }) })
    render(<App />)
    expect(await screen.findByText('Character: Alice')).toBeInTheDocument()
    expect(screen.queryByTestId('password-input')).not.toBeInTheDocument()
  })
})
