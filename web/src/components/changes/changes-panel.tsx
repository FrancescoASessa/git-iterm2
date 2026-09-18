import { useEffect } from 'preact/hooks'

import { ApiError, discard, openDiffSplit, stage, unstage } from '../../api/client'
import { snapshot } from '../../state/repo'
import { askConfirm, pushToast, selectedFile } from '../../state/ui'
import { DiffView } from '../diff/diff-view'
import { EmptyState } from '../common/empty-state'
import { CommitBox } from './commit-box'
import { FileGroup } from './file-group'
import { FileRow } from './file-row'
import type { FileChange, RepoSnapshot } from '../../api/types'

export function orderedFiles(): Array<{ path: string; staged: boolean }> {
  const current = snapshot.value
  if (current === null) return []
  return [
    ...current.conflicted.map((file) => ({ path: file.path, staged: false })),
    ...current.staged.map((file) => ({ path: file.path, staged: true })),
    ...current.unstaged.map((file) => ({ path: file.path, staged: false })),
    ...current.untracked.map((path) => ({ path, staged: false })),
  ]
}

// A snapshot can move the selected file to the other side (stage/unstage) or
// remove it entirely (discard, commit, external edit). Follow the path to the
// side it now lives on, or drop the selection so no stale diff box is left.
function reconcileSelection(current: RepoSnapshot): void {
  const selected = selectedFile.value
  if (selected === null) return
  const onStaged = current.staged.some((file) => file.path === selected.path)
  const onWorktree =
    current.unstaged.some((file) => file.path === selected.path) ||
    current.conflicted.some((file) => file.path === selected.path) ||
    current.untracked.includes(selected.path)
  if (selected.staged ? onStaged : onWorktree) return
  if (onStaged) selectedFile.value = { path: selected.path, staged: true }
  else if (onWorktree) selectedFile.value = { path: selected.path, staged: false }
  else selectedFile.value = null
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

async function confirmDiscard(paths: string[]): Promise<void> {
  const choice = await askConfirm({
    title: paths.length === 1 ? 'Discard changes?' : `Discard ${paths.length} files?`,
    body: 'The changes cannot be recovered.',
    choices: [{ id: 'discard', label: 'Discard', tone: 'danger' }],
  })
  if (choice === 'discard') await run(() => discard(paths))
}

function select(path: string, staged: boolean): void {
  selectedFile.value = { path, staged }
}

function isSelected(path: string, staged: boolean): boolean {
  const current = selectedFile.value
  return current !== null && current.path === path && current.staged === staged
}

async function openSplitForFile(path: string, staged: boolean): Promise<void> {
  try {
    await openDiffSplit(path, staged)
  } catch (error) {
    if (error instanceof ApiError) {
      pushToast({
        tone: error.code === 'UNSUPPORTED' ? 'info' : 'error',
        message: error.message,
        detail: error.stderr || undefined,
      })
    } else throw error
  }
}

function rows(files: FileChange[], staged: boolean) {
  return files.map((file) => (
    <FileRow
      key={`${staged ? 's' : 'w'}:${file.path}`}
      path={file.path}
      status={file.status}
      origPath={file.orig_path}
      staged={staged}
      selected={isSelected(file.path, staged)}
      onSelect={() => select(file.path, staged)}
      onStage={staged ? undefined : () => run(() => stage([file.path]))}
      onUnstage={staged ? () => run(() => unstage([file.path])) : undefined}
      onDiscard={staged ? undefined : () => confirmDiscard([file.path])}
      onOpenSplit={() => openSplitForFile(file.path, staged)}
    />
  ))
}

export function ChangesPanel() {
  const current = snapshot.value

  useEffect(() => {
    if (current !== null) reconcileSelection(current)
  }, [current])

  if (current === null) return null

  const untracked: FileChange[] = current.untracked.map((path) => ({
    path,
    orig_path: null,
    status: 'A',
  }))
  const total =
    current.conflicted.length + current.staged.length + current.unstaged.length + untracked.length

  if (total === 0) return <EmptyState title="No changes" />

  return (
    <div class="changes">
      <CommitBox />
      {current.conflicted.length > 0 && (
        <FileGroup title="Conflicts" count={current.conflicted.length}>
          {rows(current.conflicted, false)}
        </FileGroup>
      )}
      {current.staged.length > 0 && (
        <FileGroup
          title="Staged"
          count={current.staged.length}
          action={{
            label: 'Unstage all',
            ariaLabel: 'Unstage all staged',
            run: () => run(() => unstage(current.staged.map((file) => file.path))),
          }}
        >
          {rows(current.staged, true)}
        </FileGroup>
      )}
      {current.unstaged.length > 0 && (
        <FileGroup
          title="Changes"
          count={current.unstaged.length}
          action={{
            label: 'Stage all',
            ariaLabel: 'Stage all changes',
            run: () => run(() => stage(current.unstaged.map((file) => file.path))),
          }}
        >
          {rows(current.unstaged, false)}
        </FileGroup>
      )}
      {untracked.length > 0 && (
        <FileGroup
          title="Untracked"
          count={untracked.length}
          action={{
            label: 'Stage all',
            ariaLabel: 'Stage all untracked',
            run: () => run(() => stage(untracked.map((file) => file.path))),
          }}
        >
          {rows(untracked, false)}
        </FileGroup>
      )}
      {selectedFile.value !== null && (
        <DiffView
          revision={current}
          source={{
            kind: 'worktree',
            path: selectedFile.value.path,
            staged: selectedFile.value.staged,
          }}
        />
      )}
    </div>
  )
}
