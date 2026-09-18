import type { FileStatus } from '../../api/types'
import { useAsyncAction } from '../common/use-async-action'

export type FileRowProps = {
  path: string
  status: FileStatus
  origPath?: string | null
  staged: boolean
  selected: boolean
  onSelect: () => void
  onStage?: () => Promise<void>
  onUnstage?: () => Promise<void>
  onDiscard?: () => Promise<void>
  onOpenSplit?: () => Promise<void>
}

export function FileRow(props: FileRowProps) {
  const { pending, run } = useAsyncAction()
  const label = props.origPath ? `${props.origPath} → ${props.path}` : props.path

  const { onStage, onUnstage, onDiscard, onOpenSplit } = props
  const handleStage = onStage ? () => run(onStage) : undefined
  const handleUnstage = onUnstage ? () => run(onUnstage) : undefined
  const handleDiscard = onDiscard ? () => run(onDiscard) : undefined
  const handleOpenSplit = onOpenSplit ? () => run(onOpenSplit) : undefined

  const handlePathClick = (event: MouseEvent) => {
    if (event.altKey && handleOpenSplit) {
      handleOpenSplit()
    } else {
      props.onSelect()
    }
  }

  const handlePathDblClick = () => {
    if (handleOpenSplit) {
      handleOpenSplit()
    }
  }

  return (
    <div class={`row file-row${props.selected ? ' selected' : ''}`}>
      <span class={`status status-${props.status}`} aria-hidden="true">
        {props.status}
      </span>
      <button class="grow path" onClick={handlePathClick} onDblClick={handlePathDblClick}>
        {label}
      </button>
      {handleStage && (
        <button
          class="icon-btn"
          disabled={pending}
          aria-label={`Stage ${props.path}`}
          onClick={handleStage}
        >
          +
        </button>
      )}
      {handleUnstage && (
        <button
          class="icon-btn"
          disabled={pending}
          aria-label={`Unstage ${props.path}`}
          onClick={handleUnstage}
        >
          −
        </button>
      )}
      {handleDiscard && (
        <button
          class="icon-btn danger"
          disabled={pending}
          aria-label={`Discard ${props.path}`}
          onClick={handleDiscard}
        >
          ↺
        </button>
      )}
    </div>
  )
}
