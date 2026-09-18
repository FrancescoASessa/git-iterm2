import { computed, signal } from '@preact/signals'

import type { OpDoneMessage, OpProgressMessage } from '../api/types'
import { pushToast } from './ui'

export type RunningOp = { opId: string; phase: string; pct: number | null; line: string }

export const runningOps = signal<RunningOp[]>([])
export const isBusy = computed(() => runningOps.value.length > 0)

export function handleOpProgress(message: OpProgressMessage): void {
  const next: RunningOp = {
    opId: message.op_id,
    phase: message.phase,
    pct: message.pct,
    line: message.line,
  }
  const existing = runningOps.value.findIndex((op) => op.opId === message.op_id)
  runningOps.value =
    existing === -1
      ? [...runningOps.value, next]
      : runningOps.value.map((op, index) => (index === existing ? next : op))
}

export function handleOpDone(message: OpDoneMessage): void {
  runningOps.value = runningOps.value.filter((op) => op.opId !== message.op_id)
  if (!message.ok) {
    pushToast({
      tone: 'error',
      message: message.error?.message ?? 'Operation failed',
      detail: message.error?.stderr || undefined,
    })
  }
}
