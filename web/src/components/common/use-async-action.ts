import { useState } from 'preact/hooks'

export function useAsyncAction(): {
  pending: boolean
  run: (action: () => Promise<void>) => void
} {
  const [pending, setPending] = useState(false)

  const run = (action: () => Promise<void>): void => {
    if (pending) return
    setPending(true)
    action().finally(() => {
      setPending(false)
    })
  }

  return { pending, run }
}
