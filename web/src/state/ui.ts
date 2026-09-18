import { signal } from '@preact/signals'

import type { TabId } from '../api/types'

export type Toast = { id: number; message: string; detail?: string; tone: 'error' | 'info' }
export type DialogChoice = { id: string; label: string; tone?: 'danger' }
export type DialogRequest = {
  title: string
  body: string
  choices: DialogChoice[]
  resolve: (choice: string | null) => void
}

export const activeTab = signal<TabId>('changes')
export const selectedFile = signal<{ path: string; staged: boolean } | null>(null)
export const selectedCommit = signal<string | null>(null)
export const branchFilter = signal('')
export const toasts = signal<Toast[]>([])
export const dialog = signal<DialogRequest | null>(null)

let nextToastId = 1

export function setActiveTab(tab: TabId): void {
  activeTab.value = tab
}

export function pushToast(toast: Omit<Toast, 'id'>): void {
  toasts.value = [...toasts.value, { ...toast, id: nextToastId++ }]
}

export function dismissToast(id: number): void {
  toasts.value = toasts.value.filter((toast) => toast.id !== id)
}

export function askConfirm(request: Omit<DialogRequest, 'resolve'>): Promise<string | null> {
  return new Promise((resolve) => {
    const previous = dialog.value
    dialog.value = { ...request, resolve }
    if (previous !== null) {
      previous.resolve(null)
    }
  })
}

export function resolveDialog(choice: string | null): void {
  const current = dialog.value
  dialog.value = null
  current?.resolve(choice)
}
