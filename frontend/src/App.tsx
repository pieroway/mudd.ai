import { useState } from 'react'
import Terminal from './components/Terminal'
import './App.css'

function App() {
  const [username, setUsername] = useState<string>('')
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [inputValue, setInputValue] = useState('')

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim()) {
      setUsername(inputValue.trim())
      setIsLoggedIn(true)
      setInputValue('')
    }
  }

  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <h1>Welcome to the MUD</h1>
        <form onSubmit={handleLogin}>
          <input
            type="text"
            placeholder="Enter username"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            autoFocus
            data-testid="username-input"
          />
          <button type="submit" data-testid="login-button">
            Enter World
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="app">
      <Terminal username={username} />
    </div>
  )
}

export default App
