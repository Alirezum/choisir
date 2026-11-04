import { ref } from 'vue'

import type { WorkspaceBinding } from '../view-models.ts'
import { useBootstrap } from './use-bootstrap.ts'
import { useBrowser } from './use-browser.ts'
import { useChoice } from './use-choice.ts'
import { useFolderOptions } from './use-folder-options.ts'
import { useHistoryActions } from './use-history-actions.ts'
import { useHistorySelection } from './use-history-selection.ts'
import { usePicker } from './use-picker.ts'
import { useShortcuts } from './use-shortcuts.ts'
import { useStatus } from './use-status.ts'
import { useTabs } from './use-tabs.ts'
import { useWorkspaceState } from './use-workspace-state.ts'

/**
 * Composition only: instantiate the units, connect path/log reset callbacks,
 * and expose the binding surface. No validation, messages, API calls, timers,
 * or workflow rules live here.
 */
export function useWorkspace(): WorkspaceBinding {
  const status = useStatus()
  const options = useFolderOptions()
  const choice = useChoice()
  const pathInput = ref<HTMLInputElement | null>(null)

  function resetOnPathChange(): void {
    choice.invalidate()
    selection.clear()
    historyActions.cancelDelete()
  }

  function resetOnLogChange(): void {
    selection.clear()
    historyActions.cancelDelete()
  }

  function selectHistoryItem(item: string, shift: boolean): void {
    const applied = selection.select(item, shift)
    if (applied && !shift) void historyActions.previewHistoryItem(item)
  }

  const workspaceState = useWorkspaceState({
    path: options.path,
    logFile: options.logFile,
    includeHidden: options.includeHidden,
    mode: options.mode,
    filters: options.filters,
    status,
    onPathChange: resetOnPathChange,
    onLogChange: resetOnLogChange,
  })

  const selection = useHistorySelection({
    entries: () => workspaceState.state.value?.history ?? [],
  })
  const picker = usePicker({
    options,
    choice,
    status,
    refresh: workspaceState.refresh,
    pathInput,
  })
  const historyActions = useHistoryActions({
    options,
    choice,
    selection,
    state: workspaceState.state,
    status,
    refresh: workspaceState.refresh,
    openEntry: picker.openEntry,
  })
  const tabs = useTabs({ state: workspaceState.state })
  const browser = useBrowser({
    path: options.path,
    useFolder: (target) => {
      options.path.value = target
    },
    status,
  })

  useShortcuts({ pick: picker.pick, clearing: historyActions.clearing })
  useBootstrap({
    options,
    refresh: workspaceState.refresh,
    status,
  })

  return {
    pathInput,
    tabs: tabs.tabs,

    path: options.path,
    logFile: options.logFile,
    seed: options.seed,
    dryRun: options.dryRun,
    includeHidden: options.includeHidden,
    mode: options.mode,

    status: status.status,
    state: workspaceState.state,
    choice: choice.choice,
    pickSerial: choice.pickSerial,
    activeTab: tabs.activeTab,

    clearing: historyActions.clearing,
    removingItem: historyActions.removingItem,
    removingHistory: historyActions.removingHistory,
    historyChecked: selection.checkedItems,
    historyHeader: historyActions.historyHeader,
    historyAllSelected: selection.allSelected,
    historyCheckedCount: selection.checkedCount,
    pendingHistoryDelete: historyActions.pendingHistoryDelete,
    historyDeleteCount: historyActions.historyDeleteCount,
    historyDeleteMessage: historyActions.historyDeleteMessage,
    historyDeleteLabel: historyActions.historyDeleteLabel,

    browserListing: browser.listing,
    browserError: browser.error,

    tabCounts: tabs.counts,

    pick: picker.pick,
    openCurrent: picker.openCurrent,
    openHistoryItem: historyActions.openHistoryItem,
    previewHistoryItem: historyActions.previewHistoryItem,
    archiveHistory: historyActions.archive,
    requestClear: historyActions.requestClear,
    confirmClear: historyActions.confirmClear,
    cancelClear: historyActions.cancelClear,
    removeHistoryItem: historyActions.removeOne,
    selectHistoryItem,
    toggleAllHistory: selection.toggleAll,
    requestDeleteSelected: historyActions.requestDeleteSelected,
    confirmDeleteSelected: historyActions.confirmDeleteSelected,
    cancelDeleteSelected: historyActions.cancelDelete,
    onTabSelect: tabs.select,
    onTabKey: tabs.onKey,
    navigateBrowser: browser.navigate,
    useBrowserFolder: browser.useThisFolder,
  }
}
