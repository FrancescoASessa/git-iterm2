import { useEffect } from 'preact/hooks'

import { ApiError, stage, unstage } from '../../api/client'
import { activeTab, dialog, pushToast, selectedFile, setActiveTab } from '../../state/ui'
import { orderedFiles } from '../changes/changes-panel'
import type { TabId } from '../../api/types'

const TAB_KEYS: Record<string, TabId> = {
  '1': 'changes',
  '2': 'branches',
  '3': 'graph',
  '4': 'stash',
}

function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  const tag = element?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || element?.isContentEditable === true
}

function move(delta: number): void {
  const files = orderedFiles()
  if (files.length === 0) return
  const current = selectedFile.value
  const index =
    current === null
      ? -1
      : files.findIndex((file) => file.path === current.path && file.staged === current.staged)
  const next = Math.min(files.length - 1, Math.max(0, index + delta))
  selectedFile.value = files[next] ?? null
}

async function run(action: () => Promise<void>): Promise<void> {
  try {
    await action()
  } catch (error) {
    if (error instanceof ApiError)
      pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
    else throw error
  }
}

export function useKeyboardShortcuts(): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      // A confirmation dialog is modal: nothing behind it may react to a key.
      if (dialog.value !== null) return
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return
      const tab = TAB_KEYS[event.key]
      if (tab !== undefined) {
        setActiveTab(tab)
        return
      }
      const selected = selectedFile.value
      if (event.key === 'j') move(1)
      else if (event.key === 'k') move(-1)
      else if (event.key === 's' && selected !== null && !selected.staged)
        void run(() => stage([selected.path]))
      else if (event.key === 'u' && selected !== null && selected.staged)
        void run(() => unstage([selected.path]))
      else if (event.key === '/' && activeTab.value === 'branches') {
        event.preventDefault()
        document.querySelector<HTMLInputElement>('input[aria-label="Filter branches"]')?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])
}
