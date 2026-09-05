import { useEffect, useState } from 'react'
import Terminal from './components/Terminal'
import { authRequest } from './services/api'
import './App.css'

function App() {
  const [username, setUsername] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [password, setPassword] = useState('')
  const [registering, setRegistering] = useState(false)
  const [checking, setChecking] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    authRequest('/auth/me').then((identity) => {
      if (active) setUsername(identity.username)
    }).catch(() => {}).finally(() => { if (active) setChecking(false) })
    return () => { active = false }
  }, [])

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const identity = await authRequest(registering ? '/auth/register' : '/auth/login', {
        username: inputValue.trim(), password,
      })
      setUsername(identity.username)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not sign in.')
    } finally {
      setPassword('')
      setBusy(false)
    }
  }

  const logout = async () => {
    setBusy(true)
    try {
      await authRequest('/auth/logout', {})
      setUsername(null)
      setError('')
    } catch {
      setError('Could not sign out. Please try again.')
    } finally { setBusy(false) }
  }

  if (checking) return <div className="login-container">Checking session…</div>

  if (username === null) {
    return <div className="login-container">
      <h1>Welcome to the MUD</h1>
      <form onSubmit={handleLogin}>
        <label>Username
          <input value={inputValue} onChange={(event) => setInputValue(event.target.value)}
            autoComplete="username" required maxLength={50} autoFocus data-testid="username-input" />
        </label>
        <label>Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)}
            autoComplete={registering ? 'new-password' : 'current-password'} required
            minLength={registering ? 8 : 1} maxLength={128}
            pattern={registering ? String.raw`(?=.*[0-9])(?=.*[^\p{L}\p{N}\s]).*` : undefined}
            title={registering ? 'Use 8–128 characters, including a number (0-9) and a special character.' : undefined}
            data-testid="password-input" />
        </label>
        {registering && <p>Use 8–128 characters, including a number (0-9) and a special character.</p>}
        <button type="submit" disabled={busy} data-testid="login-button">
          {busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'}
        </button>
        <button type="button" disabled={busy} data-testid="register-toggle" onClick={() => {
          setRegistering(!registering); setError(''); setPassword('')
        }}>{registering ? 'Already have an account? Sign in' : 'Create a new account'}</button>
      </form>
      {error && <p role="alert">{error}</p>}
    </div>
  }

  return <div className="app">
    <button className="logout-button" onClick={logout} disabled={busy} data-testid="logout-button">Sign out</button>
    {error && <p role="alert">{error}</p>}
    <Terminal username={username} />
  </div>
}

export default App
