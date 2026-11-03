import { nextTick, ref, type Ref } from 'vue'

import type { StateResponse } from '../types.ts'
import type { PanelTab, TabId } from '../view-models.ts'

export const PANEL_TABS: readonly PanelTab[] = [
  { id: 'remaining', label: 'Remaining' },
  { id: 'history', label: 'History' },
  { id: 'browse', label: 'Browse' },
  { id: 'options', label: 'Options' },
]

export interface TabsDeps {
  state: Ref<StateResponse | null>
}

export interface TabsBinding {
  tabs: readonly PanelTab[]
  activeTab: Ref<TabId>
  select: (id: TabId) => void
  count: (id: TabId) => number | null
  onKey: (event: KeyboardEvent, id: TabId) => void
}

/**
 * Owns the active tab, the visible counts, and keyboard tab navigation.
 */
export function useTabs(deps: TabsDeps): TabsBinding {
  const activeTab = ref<TabId>('remaining')

  function select(id: TabId): void {
    activeTab.value = id
  }

  function count(id: TabId): number | null {
    if (deps.state.value === null) return null
    if (id === 'remaining') return deps.state.value.remaining_total
    if (id === 'history') return deps.state.value.history_total
    return null
  }

  function onKey(event: KeyboardEvent, id: TabId): void {
    const current = PANEL_TABS.findIndex((tab) => tab.id === id)
    let next = current
    if (event.key === 'ArrowRight') {
      next = (current + 1) % PANEL_TABS.length
    } else if (event.key === 'ArrowLeft') {
      next = (current - 1 + PANEL_TABS.length) % PANEL_TABS.length
    } else if (event.key === 'Home') {
      next = 0
    } else if (event.key === 'End') {
      next = PANEL_TABS.length - 1
    } else {
      return
    }
    event.preventDefault()
    const target = PANEL_TABS[next]
    if (target === undefined) return
    activeTab.value = target.id
    void nextTick(() => document.getElementById(`tab-${target.id}`)?.focus())
  }

  return { tabs: PANEL_TABS, activeTab, select, count, onKey }
}
