import { useState } from 'preact/hooks'

import { dismissToast, toasts, type Toast } from '../../state/ui'

function ToastRow({ toast }: { toast: Toast }) {
  const [open, setOpen] = useState(false)
  return (
    <div class={`toast toast-${toast.tone}`} role="alert">
      <div class="row">
        <span class="grow">{toast.message}</span>
        {toast.detail !== undefined && <button onClick={() => setOpen(!open)}>Details</button>}
        <button aria-label="Dismiss" onClick={() => dismissToast(toast.id)}>
          ✕
        </button>
      </div>
      {open && toast.detail !== undefined && <pre class="toast-detail">{toast.detail}</pre>}
    </div>
  )
}

export function ToastStack() {
  return (
    <div class="toasts">
      {toasts.value.map((toast) => (
        <ToastRow key={toast.id} toast={toast} />
      ))}
    </div>
  )
}
