import { getToken } from './client'
import type { ServerMessage } from './types'

export type WsStatus = 'connecting' | 'open' | 'closed' | 'unauthorized'

export type WsHandlers = {
  onMessage: (message: ServerMessage) => void
  onStatus: (status: WsStatus) => void
}

export type WsOptions = {
  url?: string
  backoff?: number[]
  socketFactory?: (url: string) => WebSocket
  timer?: typeof setTimeout
}

const DEFAULT_BACKOFF = [500, 1000, 2000, 4000, 8000]
const MESSAGE_TYPES = new Set(['snapshot', 'op_progress', 'op_done'])

function parseMessage(data: unknown): ServerMessage | null {
  if (typeof data !== 'string') return null
  let parsed: unknown
  try {
    parsed = JSON.parse(data)
  } catch {
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null
  const type = (parsed as { type?: unknown }).type
  if (typeof type !== 'string' || !MESSAGE_TYPES.has(type)) return null
  return parsed as ServerMessage
}

export function connectWs(handlers: WsHandlers, options: WsOptions = {}): { close: () => void } {
  const backoff = options.backoff ?? DEFAULT_BACKOFF
  const timer = options.timer ?? setTimeout
  const socketFactory = options.socketFactory ?? ((url: string) => new WebSocket(url))
  const url = options.url ?? `ws://${window.location.host}/ws`

  let stopped = false
  let attempt = 0
  let socket: WebSocket | null = null

  const open = (): void => {
    if (stopped) return
    handlers.onStatus('connecting')
    socket = socketFactory(url)
    let receivedMessage = false
    socket.onopen = () => {
      socket?.send(JSON.stringify({ type: 'auth', token: getToken() }))
      handlers.onStatus('open')
    }
    socket.onmessage = (event: MessageEvent) => {
      if (stopped) return
      const message = parseMessage(event.data)
      if (message !== null) {
        if (!receivedMessage) {
          attempt = 0
          receivedMessage = true
        }
        handlers.onMessage(message)
      }
    }
    socket.onclose = (event?: CloseEvent) => {
      socket = null
      if (stopped) return
      if (event?.code === 4401) {
        stopped = true
        handlers.onStatus('unauthorized')
        return
      }
      handlers.onStatus('closed')
      const delay = backoff[Math.min(attempt, backoff.length - 1)] ?? 8000
      attempt += 1
      timer(open, delay)
    }
  }

  open()

  return {
    close: () => {
      stopped = true
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onclose = null
        socket.close()
      }
      socket = null
    },
  }
}
