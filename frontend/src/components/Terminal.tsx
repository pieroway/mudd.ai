import { useState, useEffect, useRef } from 'react'
import Transcript from './Transcript'
import CommandPrompt from './CommandPrompt'
import InventoryPanel, { ClientState, isClientState } from './InventoryPanel'
import { apiUrl } from '../services/api'
import '../styles/Terminal.css'
import '../styles/Panels.css'

interface GameMessage {
  state?: unknown
  ai_usage?: { remaining: number; limit: number; day: string }
  type: string
  text?: string
  room_name?: string
  room_description?: string
  success?: boolean
  room_id?: string
  metadata?: {
    command_source?: 'classic' | 'ai'
  }
}

interface TerminalProps {
  username: string
}

type Theme = 'light' | 'dark' | 'techo'

const THEME_STORAGE_KEY = 'mudd-theme'
const themes: Theme[] = ['light', 'dark', 'techo']

function getSavedTheme(): Theme {
  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
  return themes.includes(savedTheme as Theme) ? (savedTheme as Theme) : 'dark'
}

export default function Terminal({ username }: TerminalProps) {
  const [transcript, setTranscript] = useState<string[]>([])
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [state, setState] = useState<ClientState>()
  const [inventoryVisible, setInventoryVisible] = useState(() =>
    window.localStorage.getItem('mudd-inventory-visible') !== 'false')
  const [aiUsage, setAIUsage] = useState<GameMessage['ai_usage']>()
  const [theme, setTheme] = useState<Theme>(getSavedTheme)
  const [commandSource, setCommandSource] = useState<'classic' | 'ai' | null>(null)
  const [debugEnabled, setDebugEnabled] = useState(false)
  const debugEnabledRef = useRef(false)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.localStorage.setItem('mudd-inventory-visible', String(inventoryVisible))
  }, [inventoryVisible])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  useEffect(() => {
    // Connect to WebSocket
    const socketUrl = apiUrl('/ws')
    socketUrl.protocol = socketUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    const websocket = new WebSocket(socketUrl.toString())

    websocket.onopen = () => {
      setConnected(true)
      console.log('Connected to server')
    }

    websocket.onmessage = (event) => {
      let message: GameMessage
      try {
        const parsed: unknown = JSON.parse(event.data)
        if (!parsed || typeof parsed !== 'object') return
        message = parsed as GameMessage
      } catch { return }
      if (isClientState(message.state)) setState(message.state)
      if (message.ai_usage) setAIUsage(message.ai_usage)
      let output = ''

      if (message.type === 'system') {
        output = message.text || ''
        if (message.room_name) {
          output += `\n\n${message.room_name}\n${message.room_description}`
        }
      } else if (message.type === 'game_output') {
        output = message.text || ''
        const source = message.metadata?.command_source
        if (source === 'classic' || source === 'ai') {
          setCommandSource(source)
        }
      } else if (message.type === 'error') {
        output = `[ERROR] ${message.text || 'Unknown server error'}`
      }

      if (output) {
        setTranscript((prev) => [...prev, output])
      }
      if (debugEnabledRef.current) {
        const details = [`type=${message.type}`]
        if (typeof message.success === 'boolean') {
          details.push(`success=${message.success}`)
        }
        if (message.room_id) {
          details.push(`room_id=${message.room_id}`)
        }
        if (message.metadata?.command_source) {
          details.push(`command_source=${message.metadata.command_source}`)
        }
        setTranscript((prev) => [...prev, `[DEBUG] ${details.join(' ')}`])
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      setTranscript((prev) => [...prev, '[ERROR] Connection failed'])
    }

    websocket.onclose = () => {
      setConnected(false)
      setState(undefined)
      setTranscript((prev) => [...prev, '[NOTICE] Disconnected from server'])
    }

    setWs(websocket)

    return () => {
      websocket.onmessage = null
      websocket.onerror = null
      websocket.onclose = null
      if (websocket.readyState === WebSocket.CONNECTING) {
        websocket.onopen = () => websocket.close()
        return
      }
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.close()
      }
    }
  }, [username])

  // Auto-scroll to bottom
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  const handleCommand = (command: string) => {
    const slashCommand = command.trim().toLowerCase().split(/\s+/)
    if (slashCommand[0] === '/panel') {
      const valid = slashCommand.length === 3 && slashCommand[1] === 'inventory'
        && ['show', 'hide'].includes(slashCommand[2])
      if (valid) setInventoryVisible(slashCommand[2] === 'show')
      setTranscript(prev => [...prev, `> ${command}`, valid
        ? `Inventory panel ${slashCommand[2] === 'show' ? 'shown' : 'hidden'}.`
        : 'Usage: /panel inventory show | hide'])
      return
    }
    if (slashCommand[0] === '/theme') {
      const requestedTheme = slashCommand[1]
      setTranscript((prev) => [...prev, `> ${command}`])

      if (slashCommand.length === 2 && themes.includes(requestedTheme as Theme)) {
        setTheme(requestedTheme as Theme)
        setTranscript((prev) => [...prev, `Theme changed to ${requestedTheme}.`])
      } else {
        setTranscript((prev) => [...prev, 'Usage: /theme light | dark | techo'])
      }
      return
    }

    if (slashCommand[0] === '/debug') {
      setTranscript((prev) => [...prev, `> ${command}`])
      const requestedState = slashCommand[1]
      if (slashCommand.length === 2 && (requestedState === 'on' || requestedState === 'off')) {
        const enabled = requestedState === 'on'
        debugEnabledRef.current = enabled
        setDebugEnabled(enabled)
        setTranscript((prev) => [...prev, `Debug output ${enabled ? 'enabled' : 'disabled'}.`])
      } else {
        setTranscript((prev) => [...prev, 'Usage: /debug on | off'])
      }
      return
    }

    if (ws && connected) {
      setTranscript((prev) => [...prev, `> ${command}`])
      ws.send(command)
    }
  }

  return (
    <div
      className="terminal"
      data-testid="terminal"
      data-theme={theme}
      data-command-source={commandSource ?? undefined}
      data-debug={debugEnabled ? 'on' : 'off'}
    >
      <div className="terminal-header">
        <div><p className="eyebrow">MUD.AI · A shared world</p><h2>{username}'s Journey</h2>
          <p data-testid="current-room">{connected ? state?.room_name ?? 'Entering the world…' : 'Offline'}</p>
        </div>
        {aiUsage && <span data-testid="ai-allowance" title={`Usage for ${aiUsage.day} UTC; refreshed after each command.`}>
          AI requests: {aiUsage.remaining}/{aiUsage.limit} remaining · resets 00:00 UTC
        </span>}
        <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '● Online' : '● Offline'}
        </span>
      </div>

      <nav className="panel-toolbar" aria-label="Game panels">
        <span>Adventure</span>
        <button type="button" aria-expanded={inventoryVisible} aria-controls="inventory-panel"
          onClick={() => setInventoryVisible(visible => !visible)}>Inventory</button>
      </nav>
      <div className={`game-layout ${inventoryVisible ? 'with-panel' : ''}`}>
        <Transcript lines={transcript} ref={transcriptEndRef} />
        {inventoryVisible && <InventoryPanel state={state} connected={connected} />}
      </div>

      <CommandPrompt onCommand={handleCommand} disabled={!connected} />
    </div>
  )
}
