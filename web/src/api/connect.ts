import { handleOpDone, handleOpProgress } from '../state/ops'
import { applySnapshot, connection } from '../state/repo'
import { setToken } from './client'
import { readTokenFromLocation } from './token'
import { connectWs, type WsOptions } from './ws'

export function startConnection(options: WsOptions = {}): { close: () => void } {
  setToken(readTokenFromLocation())
  return connectWs(
    {
      onStatus: (status) => {
        connection.value = status
      },
      onMessage: (message) => {
        if (message.type === 'snapshot') applySnapshot(message.repo)
        else if (message.type === 'op_progress') handleOpProgress(message)
        else handleOpDone(message)
      },
    },
    options,
  )
}
