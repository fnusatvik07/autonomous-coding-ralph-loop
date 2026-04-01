import type { StreamEvent } from './types'

class WS {
  private ws: WebSocket | null = null
  private onEvent: ((e: StreamEvent) => void) | null = null
  private alive = true
  private delay = 1000

  connect(onEvent: (e: StreamEvent) => void) {
    this.onEvent = onEvent
    this.alive = true
    this._open()
  }

  disconnect() {
    this.alive = false
    this.ws?.close()
  }

  private _open() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.ws = new WebSocket(`${proto}//${location.host}/ws/events`)
    this.ws.onmessage = (m) => {
      try { this.onEvent?.(JSON.parse(m.data)) } catch {}
    }
    this.ws.onopen = () => { this.delay = 1000 }
    this.ws.onclose = () => {
      if (!this.alive) return
      setTimeout(() => this._open(), this.delay)
      this.delay = Math.min(this.delay * 2, 20000)
    }
    this.ws.onerror = () => this.ws?.close()
  }
}

export const ws = new WS()
