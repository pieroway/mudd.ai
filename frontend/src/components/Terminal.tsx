import { useState, useEffect, useRef } from 'react'
import Transcript from './Transcript'
import CommandPrompt from './CommandPrompt'
import '../styles/Terminal.css'

interface GameMessage {
  type: string
  text?: string
  room_name?: string
  room_description?: string
}

interface TerminalProps {
  username: string
}

export default function Terminal({ username }: TerminalProps) {
  const [transcript, setTranscript] = useState<string[]>([])
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Connect to WebSocket
    const apiUrl = new URL(import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000`)
    if (apiUrl.hostname === 'localhost' && window.location.hostname !== 'localhost') {
      apiUrl.hostname = window.location.hostname
    }
    apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    apiUrl.pathname = '/ws'
    apiUrl.search = new URLSearchParams({ username }).toString()
    const websocket = new WebSocket(apiUrl.toString())

    websocket.onopen = () => {
      setConnected(true)
      console.log('Connected to server')
    }

    websocket.onmessage = (event) => {
      const message: GameMessage = JSON.parse(event.data)
      let output = ''

      if (message.type === 'system') {
        output = message.text || ''
        if (message.room_name) {
          output += `\n\n${message.room_name}\n${message.room_description}`
        }
      } else if (message.type === 'game_output') {
        output = message.text || ''
      } else if (message.type === 'error') {
        output = `[ERROR] ${message.text || 'Unknown server error'}`
      }

      if (output) {
        setTranscript((prev) => [...prev, output])
      }
    }

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
      setTranscript((prev) => [...prev, '[ERROR] Connection failed'])
    }

    websocket.onclose = () => {
      setConnected(false)
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
    if (ws && connected) {
      setTranscript((prev) => [...prev, `> ${command}`])
      ws.send(command)
    }
  }

  return (
    <div className="terminal" data-testid="terminal">
      <div className="terminal-header">
        <h2>{username}'s Journey</h2>
        <span className={`status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? '● Online' : '● Offline'}
        </span>
      </div>

      <Transcript lines={transcript} ref={transcriptEndRef} />

      <CommandPrompt onCommand={handleCommand} disabled={!connected} />
    </div>
  )
}
