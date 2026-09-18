import { beforeEach, describe, expect, it } from 'vitest'

import { setToken } from '../../src/api/client'
import { connectWs } from '../../src/api/ws'
import type { ServerMessage } from '../../src/api/types'

class FakeSocket {
  static instances: FakeSocket[] = []
  readonly sent: string[] = []
  onopen: (() => void) | null = null
  onclose: ((event?: { code?: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  closed = false

  constructor(readonly url: string) {
    FakeSocket.instances.push(this)
  }

  send(data: string): void {
    this.sent.push(data)
  }

  close(event?: { code?: number }): void {
    this.closed = true
    this.onclose?.(event)
  }
}

function connect() {
  const messages: ServerMessage[] = []
  const statuses: string[] = []
  const timers: Array<{ delay: number; run: () => void }> = []
  const timer = ((callback: () => void, delay: number) => {
    timers.push({ delay, run: callback })
    return timers.length
  }) as unknown as typeof setTimeout

  const handle = connectWs(
    { onMessage: (message) => messages.push(message), onStatus: (status) => statuses.push(status) },
    { socketFactory: (url) => new FakeSocket(url) as unknown as WebSocket, timer },
  )
  return { handle, messages, statuses, timers }
}

describe('connectWs', () => {
  beforeEach(() => {
    FakeSocket.instances = []
    setToken('tok')
  })

  it('authenticates first and reports open', () => {
    const { statuses } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket = FakeSocket.instances[0] as FakeSocket

    expect(statuses[0]).toBe('connecting')
    socket.onopen?.()

    expect(socket.sent.length).toBeGreaterThan(0)
    expect(JSON.parse(socket.sent[0] as string)).toEqual({ type: 'auth', token: 'tok' })
    expect(statuses).toContain('open')
    expect(socket.url).toContain('/ws')
  })

  it('forwards valid messages and ignores malformed frames', () => {
    const { messages } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket = FakeSocket.instances[0] as FakeSocket
    socket.onopen?.()

    socket.onmessage?.({ data: 'not json' })
    socket.onmessage?.({ data: JSON.stringify({ type: 'nope' }) })
    socket.onmessage?.({ data: JSON.stringify({ type: 'snapshot', repo: null }) })

    expect(messages).toEqual([{ type: 'snapshot', repo: null }])
  })

  it('reconnects with growing backoff', () => {
    const { statuses, timers } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket0 = FakeSocket.instances[0] as FakeSocket
    socket0.onopen?.()
    socket0.close()

    expect(statuses).toContain('closed')
    expect(timers.length).toBeGreaterThan(0)
    const timer0 = timers[0] as { delay: number; run: () => void }
    expect(timer0.delay).toBe(500)
    timer0.run()
    expect(FakeSocket.instances).toHaveLength(2)

    const socket1 = FakeSocket.instances[1] as FakeSocket
    socket1.close()
    expect(timers.length).toBeGreaterThan(1)
    const timer1 = timers[1] as { delay: number; run: () => void }
    expect(timer1.delay).toBe(1000)
  })

  it('stops reconnecting after close()', () => {
    const { handle, timers } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket = FakeSocket.instances[0] as FakeSocket
    socket.onopen?.()
    handle.close()
    socket.close()
    expect(timers).toHaveLength(0)
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('backs off when the server keeps closing the socket after the handshake', () => {
    const { timers } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket0 = FakeSocket.instances[0] as FakeSocket
    socket0.onopen?.()
    socket0.close()

    for (let i = 0; i < 5; i++) {
      expect(timers.length).toBeGreaterThan(i)
      const timer = timers[i] as { delay: number; run: () => void }
      const expectedDelays = [500, 1000, 2000, 4000, 8000]
      expect(timer.delay).toBe(expectedDelays[i])
      if (i < 4) {
        timer.run()
        expect(FakeSocket.instances.length).toBe(i + 2)
        const nextSocket = FakeSocket.instances[i + 1] as FakeSocket
        nextSocket.close()
      }
    }
  })

  it('resets the backoff after a real message', () => {
    const { timers } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket0 = FakeSocket.instances[0] as FakeSocket
    socket0.onopen?.()

    socket0.onmessage?.({ data: JSON.stringify({ type: 'snapshot', repo: null }) })
    socket0.close()

    expect(timers.length).toBeGreaterThan(0)
    const timer0 = timers[0] as { delay: number; run: () => void }
    expect(timer0.delay).toBe(500)
    timer0.run()

    expect(FakeSocket.instances).toHaveLength(2)
    const socket1 = FakeSocket.instances[1] as FakeSocket
    socket1.close()

    expect(timers.length).toBeGreaterThan(1)
    const timer1 = timers[1] as { delay: number; run: () => void }
    expect(timer1.delay).toBe(1000)
  })

  it('stops reconnecting and reports unauthorized on close code 4401', () => {
    const { statuses, timers } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket = FakeSocket.instances[0] as FakeSocket

    socket.onopen?.()
    socket.close({ code: 4401 })

    expect(statuses).toContain('unauthorized')
    expect(timers).toHaveLength(0)
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('delivers no message after close()', () => {
    const { handle, messages } = connect()
    expect(FakeSocket.instances.length).toBeGreaterThan(0)
    const socket = FakeSocket.instances[0] as FakeSocket

    socket.onopen?.()
    const capturedOnmessage = socket.onmessage
    handle.close()

    capturedOnmessage?.({ data: JSON.stringify({ type: 'snapshot', repo: null }) })

    expect(messages).toHaveLength(0)
  })
})
