import { activeTab, setActiveTab } from '../state/ui'
import type { TabId } from '../api/types'

const TABS: Array<{ id: TabId; label: string }> = [
  { id: 'changes', label: 'Changes' },
  { id: 'branches', label: 'Branches' },
  { id: 'graph', label: 'Graph' },
  { id: 'stash', label: 'Stash' },
]

export function Tabs() {
  return (
    <div role="tablist" aria-label="Panel sections" class="tabs">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={activeTab.value === tab.id}
          onClick={() => setActiveTab(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
