import { useState, useRef, useEffect } from 'react'

interface CommandPromptProps {
  onCommand: (command: string) => void
  disabled?: boolean
}

export default function CommandPrompt({ onCommand, disabled = false }: CommandPromptProps) {
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onCommand(input.trim())
      setHistory((prev) => [...prev, input.trim()])
      setHistoryIndex(-1)
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      const newIndex = historyIndex + 1
      if (newIndex < history.length) {
        setHistoryIndex(newIndex)
        setInput(history[history.length - 1 - newIndex])
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const newIndex = historyIndex - 1
      if (newIndex >= 0) {
        setHistoryIndex(newIndex)
        setInput(history[history.length - 1 - newIndex])
      } else {
        setHistoryIndex(-1)
        setInput('')
      }
    }
  }

  useEffect(() => {
    if (!disabled) {
      inputRef.current?.focus()
    }
  }, [disabled])

  return (
    <form onSubmit={handleSubmit} className="command-prompt">
      <span className="prompt-symbol">{'>'}</span>
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter a command..."
        disabled={disabled}
        data-testid="command-input"
        autoFocus
      />
      <button type="submit" disabled={disabled}>
        Send
      </button>
    </form>
  )
}
