import { useState } from 'preact/hooks'
import type { ComponentChildren } from 'preact'
import { useAsyncAction } from '../common/use-async-action'

export type GroupAction = { label: string; ariaLabel: string; run: () => Promise<void> }

export function FileGroup({
  title,
  count,
  action,
  children,
}: {
  title: string
  count: number
  action?: GroupAction
  children: ComponentChildren
}) {
  const [open, setOpen] = useState(true)
  const { pending, run } = useAsyncAction()

  return (
    <section>
      <div class="row group-header">
        <button class="grow section-title" aria-expanded={open} onClick={() => setOpen(!open)}>
          {title}
        </button>
        <span class="count">{count}</span>
        {action && (
          <button
            class="btn"
            disabled={pending}
            aria-label={action.ariaLabel}
            onClick={() => run(action.run)}
          >
            {action.label}
          </button>
        )}
      </div>
      {open && children}
    </section>
  )
}
