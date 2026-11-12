import { computed, ref } from 'vue'

import type { FilterOptions } from '../types.ts'
import type { WorkspaceBinding } from '../view-models.ts'
import { useBootstrap } from './use-bootstrap.ts'
import { useBrowser } from './use-browser.ts'
import { useChoice } from './use-choice.ts'
import { useFilters } from './use-filters.ts'
import { useFolderOptions } from './use-folder-options.ts'
import { useHistoryActions } from './use-history-actions.ts'
import { useHistorySelection } from './use-history-selection.ts'
import { usePathMemory } from './use-path-memory.ts'
import { usePicker } from './use-picker.ts'
import { useShortcuts } from './use-shortcuts.ts'
import { useStatus } from './use-status.ts'
import { useTabs } from './use-tabs.ts'
import { useWorkspaceState } from './use-workspace-state.ts'

const EMPTY_FILTER_OPTIONS: FilterOptions = {
  types: [],
  entries: [],
  entries_total: 0,
  entries_truncated: false,
}

/**
 * Composition only: instantiate the units, connect path/log reset callbacks,
 * and expose the binding surface. No validation, messages, API calls, timers,
 * or workflow rules live here.
 */
export function useWorkspace(): WorkspaceBinding {
  const status = useStatus()
  const options = useFolderOptions()
  const pathMemory = usePathMemory({ status })
  const choice = useChoice()
  const filterState = useFilters({
    path: options.path,
    logFile: options.logFile,
  })
  const pathInput = ref<HTMLInputElement | null>(null)

  function resetOnPathChange(): void {
    choice.invalidate()
    selection.clear()
    historyActions.cancelDelete()
    filterState.reset()
  }

  function resetOnLogChange(): void {
    selection.clear()
    historyActions.cancelDelete()
    filterState.reset()
  }

  function selectHistoryItem(item: string, shift: boolean): void {
    const applied = selection.select(item, shift)
    if (applied && !shift) void historyActions.previewHistoryItem(item)
  }

  const workspaceState = useWorkspaceState({
    path: options.path,
    logFile: options.logFile,
    folderFlags: options.folderFlags,
    filterExclusions: filterState.exclusions,
    status,
    onPathChange: resetOnPathChange,
    onLogChange: resetOnLogChange,
    onState: (response) => {
      filterState.reconcile(
        response?.filter_options ?? EMPTY_FILTER_OPTIONS,
        response?.known_entry_exclusions ?? [],
      )
    },
  })

  const selection = useHistorySelection({
    entries: () => workspaceState.state.value?.history ?? [],
  })
  const picker = usePicker({
    options,
    choice,
    status,
    refresh: workspaceState.refresh,
    refreshPathMemory: pathMemory.refresh,
    pathInput,
    filterExclusions: filterState,
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

  const filterPanel = computed(() =>
    filterState.panel(
      workspaceState.state.value?.filter_options ?? null,
      workspaceState.state.value?.remaining_total ?? 0,
      workspaceState.state.value?.valid_path ?? false,
    ),
  )

  useShortcuts({ pick: picker.pick, clearing: historyActions.clearing })
  useBootstrap({
    options,
    refresh: workspaceState.refresh,
    refreshPathMemory: pathMemory.refresh,
    status,
  })

  function activateRecentPath(target: string): void {
    options.path.value = target
  }

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

    filterPanel,

    recentPaths: pathMemory.recent,
    pathMemoryWarning: pathMemory.warning,
    pathMemoryNotice: pathMemory.notice,
    activateRecentPath,
    removeRecentPath: pathMemory.remove,
    clearRecentPaths: pathMemory.clear,

    toggleFilterType: filterState.toggleType,
    toggleFilterEntry: filterState.toggleEntry,
    selectAllFilterTypes: filterState.selectAllTypes,
    clearFilterTypes: filterState.clearTypes,
    selectAllFilterEntries: filterState.selectAllEntries,
    clearFilterEntries: filterState.clearEntries,
    clearFilters: filterState.clearFilters,

    clearing: historyActions.clearing,
    removingItem: historyActions.removingItem,
    removingHistory: historyActions.removingHistory,
    historyChecked: selection.checkedItems,
    historyHeader: historyActions.historyHeader,
    historyAllSelected: selection.allSelected,
    historyCheckedCount: selection.checkedCount,
    pendingHistoryDelete: historyActions.pendingHistoryDelete,
    clearMessage: historyActions.clearMessage,
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
