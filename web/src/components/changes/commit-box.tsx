import { useState } from 'preact/hooks'

import { ApiError, commit } from '../../api/client'
import { snapshot } from '../../state/repo'
import { pushToast } from '../../state/ui'

export function CommitBox() {
  const [message, setMessage] = useState('')
  const [amend, setAmend] = useState(false)
  const [pending, setPending] = useState(false)
  const staged = snapshot.value?.staged.length ?? 0
  const canCommit = !pending && (amend || (message.trim().length > 0 && staged > 0))

  const submit = async (): Promise<void> => {
    if (!canCommit) return
    setPending(true)
    try {
      await commit(message, amend)
      setMessage('')
      setAmend(false)
    } catch (error) {
      if (error instanceof ApiError)
        pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
      else throw error
    } finally {
      setPending(false)
    }
  }

  return (
    <div class="commit-box">
      <label class="visually-hidden" for="commit-message">
        Commit message
      </label>
      <textarea
        id="commit-message"
        rows={2}
        placeholder="Commit message"
        value={message}
        onInput={(event) => setMessage((event.target as HTMLTextAreaElement).value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
            event.preventDefault()
            void submit()
          }
        }}
      />
      <div class="row">
        <label class="grow">
          <input
            type="checkbox"
            aria-label="Amend"
            checked={amend}
            onChange={(event) => setAmend((event.target as HTMLInputElement).checked)}
          />{' '}
          Amend
        </label>
        <button class="btn btn-primary" disabled={!canCommit} onClick={() => void submit()}>
          Commit
        </button>
      </div>
    </div>
  )
}
