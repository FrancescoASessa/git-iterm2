import './styles.css'

import { BranchesPanel } from './components/branches/branches-panel'
import { ChangesPanel } from './components/changes/changes-panel'
import { Banner, RepoStateBanner } from './components/common/banner'
import { ConfirmDialog } from './components/common/confirm-dialog'
import { EmptyState } from './components/common/empty-state'
import { useKeyboardShortcuts } from './components/common/keyboard'
import { ToastStack } from './components/common/toast'
import { GraphPanel } from './components/graph/graph-panel'
import { Header } from './components/header'
import { StashPanel } from './components/stash/stash-panel'
import { Tabs } from './components/tabs'
import { connection, hasRepo, receivedSnapshot, shellIntegration } from './state/repo'
import { activeTab } from './state/ui'

function ActivePanel() {
  switch (activeTab.value) {
    case 'changes':
      return <ChangesPanel />
    case 'branches':
      return <BranchesPanel />
    case 'graph':
      return <GraphPanel />
    default:
      return <StashPanel />
  }
}

export function App() {
  useKeyboardShortcuts()
  return (
    <div class="app">
      {connection.value === 'unauthorized' ? (
        <Banner>Unauthorized — reopen the panel from iTerm2</Banner>
      ) : (
        // Only a closed socket is worth a banner: `connecting` is the very
        // first paint, where "Disconnected — reconnecting…" is simply wrong.
        connection.value === 'closed' && <Banner>Disconnected — reconnecting…</Banner>
      )}
      <Header />
      <RepoStateBanner />
      <Tabs />
      <div class="panel">
        {!receivedSnapshot.value ? (
          <EmptyState title="Loading…" />
        ) : hasRepo.value ? (
          <ActivePanel />
        ) : shellIntegration.value === false ? (
          <EmptyState
            title="Shell Integration not enabled"
            hint="iTerm2 cannot tell which directory this session is in. Install it from iTerm2 › Install Shell Integration, then reopen the panel."
          />
        ) : (
          <EmptyState title="Not a git repository" hint="cd into a repository in this session." />
        )}
      </div>
      <ToastStack />
      <ConfirmDialog />
    </div>
  )
}
