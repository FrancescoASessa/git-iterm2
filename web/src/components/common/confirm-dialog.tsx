import { useEffect, useRef } from 'preact/hooks'

import { dialog, resolveDialog } from '../../state/ui'

export function ConfirmDialog() {
  const request = dialog.value
  const container = useRef<HTMLDivElement | null>(null)
  const firstButton = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (request === null) return
    firstButton.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' || event.code === 'Escape' || event.keyCode === 27) {
        event.preventDefault()
        resolveDialog(null)
        return
      }
      if (event.key !== 'Tab') return
      // aria-modal alone does not stop Tab from walking into the rows behind
      // the backdrop, so wrap focus around the dialog's own buttons.
      const node = container.current
      if (node === null) return
      const buttons = Array.from(node.querySelectorAll<HTMLButtonElement>('button'))
      const first = buttons[0]
      const last = buttons[buttons.length - 1]
      if (first === undefined || last === undefined) return
      const active = document.activeElement
      const inside = active !== null && node.contains(active)
      if (event.shiftKey) {
        if (!inside || active === first) {
          event.preventDefault()
          last.focus()
        }
      } else if (!inside || active === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [request])

  if (request === null) return null

  return (
    <div class="dialog-backdrop">
      <div
        class="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={request.title}
        ref={container}
      >
        <h2>{request.title}</h2>
        <p>{request.body}</p>
        <div class="row dialog-actions">
          {request.choices.map((choice, index) => (
            <button
              key={choice.id}
              ref={index === 0 ? firstButton : undefined}
              class={choice.tone === 'danger' ? 'danger' : undefined}
              onClick={() => resolveDialog(choice.id)}
            >
              {choice.label}
            </button>
          ))}
          <button onClick={() => resolveDialog(null)}>Cancel</button>
        </div>
      </div>
    </div>
  )
}
