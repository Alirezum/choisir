import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { StateResponse } from '../types.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { HistorySelectionBinding } from './use-history-selection.ts'
import type { StatusBinding } from './use-status.ts'

export interface HistoryActionsDeps {
  options: Pick<FolderOptionsBinding, 'path' | 'logFile' | 'entryPath'>
  choice: Pick<ChoiceBinding, 'beginPreview' | 'applyPreview' | 'isCurrent'>
  selection: Pick<HistorySelectionBinding, 'checkedItems' | 'clear' | 'remove'>
  state: Ref<StateResponse | null>
  status: Pick<StatusBinding, 'setStatus' | 'reportError'>
  refresh: () => Promise<void>
  openEntry: (entry: string) => Promise<void>
}

export interface HistoryActionsBinding {
  clearing: Ref<boolean>
  removingItem: Ref<string | null>
  removingHistory: Ref<boolean>
  pendingHistoryDelete: Ref<string[] | null>
  historyHeader: ComputedRef<string>
  historyDeleteCount: ComputedRef<number>
  historyDeleteMessage: ComputedRef<string>
  historyDeleteLabel: ComputedRef<string>
  archive: () => Promise<void>
  requestClear: () => void
  confirmClear: () => Promise<void>
  cancelClear: () => void
  removeOne: (item: string) => Promise<void>
  requestDeleteSelected: () => void
  confirmDeleteSelected: () => Promise<void>
  cancelDelete: () => void
  previewHistoryItem: (item: string) => Promise<void>
  openHistoryItem: (item: string) => void
}

/**
 * Owns archive, clear, single removal, batch removal, their confirmations and
 * busy flags, and preview/open-from-history. Exact messages are preserved.
 */
export function useHistoryActions(
  deps: HistoryActionsDeps,
): HistoryActionsBinding {
  const { options, choice, selection, status } = deps

  const clearing = ref(false)
  const removingItem = ref<string | null>(null)
  const removingHistory = ref(false)
  const pendingHistoryDelete = ref<string[] | null>(null)

  const historyHeader = computed(() => {
    const entries = deps.state.value?.history ?? []
    const total = deps.state.value?.history_total ?? 0
    if (entries.length < total) {
      return `${total} picked (showing the last ${entries.length})`
    }
    return `${total} picked`
  })
  const historyDeleteCount = computed(
    () => pendingHistoryDelete.value?.length ?? 0,
  )
  const historyDeleteMessage = computed(() => {
    const count = historyDeleteCount.value
    if (count === 0) return ''
    const noun = count === 1 ? 'item' : 'items'
    return `Delete history for ${count} ${noun}?\nThis removes every log entry for the selected items, making them pickable again.`
  })
  const historyDeleteLabel = computed(() => {
    const count = historyDeleteCount.value
    return count === 1 ? 'Delete 1 item' : `Delete ${count} items`
  })

  async function archive(): Promise<void> {
    try {
      const result = await api.archive(options.path.value, options.logFile.value)
      status.setStatus(
        result.backup === null
          ? `No history file at ${result.log_file}.`
          : `Archived history to ${result.backup}.`,
      )
    } catch (error) {
      status.reportError(error)
    } finally {
      await deps.refresh()
      selection.clear()
    }
  }

  function requestClear(): void {
    clearing.value = true
  }

  async function confirmClear(): Promise<void> {
    clearing.value = false
    try {
      const result = await api.clear(options.path.value, options.logFile.value)
      status.setStatus(
        result.removed
          ? `Cleared ${result.log_file}.`
          : `No history file at ${result.log_file}.`,
      )
    } catch (error) {
      status.reportError(error)
    } finally {
      await deps.refresh()
      selection.clear()
    }
  }

  function cancelClear(): void {
    clearing.value = false
  }

  async function removeOne(item: string): Promise<void> {
    if (removingItem.value !== null) return
    removingItem.value = item
    try {
      const result = await api.removeHistoryItem(
        options.path.value,
        options.logFile.value,
        item,
      )
      if (result.removed === 0) {
        status.setStatus(`No history entry for "${item}".`)
      } else if (result.removed === 1) {
        status.setStatus(`Removed "${item}" from history.`)
      } else {
        status.setStatus(`Removed ${result.removed} entries for "${item}".`)
      }
    } catch (error) {
      status.reportError(error)
    } finally {
      removingItem.value = null
      selection.remove([item])
      await deps.refresh()
    }
  }

  function requestDeleteSelected(): void {
    if (selection.checkedItems.value.length === 0) return
    pendingHistoryDelete.value = [...selection.checkedItems.value]
  }

  async function confirmDeleteSelected(): Promise<void> {
    const items = pendingHistoryDelete.value
    if (items === null) return
    pendingHistoryDelete.value = null
    removingHistory.value = true
    try {
      const result = await api.removeHistoryItems(
        options.path.value,
        options.logFile.value,
        items,
      )
      if (result.removed === 0) {
        status.setStatus('No matching history entries to remove.')
      } else if (result.removed === 1) {
        status.setStatus('Removed 1 entry from history.')
      } else {
        status.setStatus(`Removed ${result.removed} entries from history.`)
      }
    } catch (error) {
      status.reportError(error)
    } finally {
      removingHistory.value = false
      selection.remove(items)
      await deps.refresh()
    }
  }

  function cancelDelete(): void {
    pendingHistoryDelete.value = null
  }

  async function previewHistoryItem(item: string): Promise<void> {
    const request = choice.beginPreview({
      item,
      path: options.entryPath(item),
      preview: null,
    })
    try {
      const preview = await api.preview(options.entryPath(item))
      if (!choice.isCurrent(request)) return
      choice.applyPreview(request, preview)
      status.setStatus(`Previewing ${item} from history.`)
    } catch (error) {
      if (!choice.isCurrent(request)) return
      status.reportError(error)
    }
  }

  function openHistoryItem(item: string): void {
    void deps.openEntry(options.entryPath(item))
  }

  return {
    clearing,
    removingItem,
    removingHistory,
    pendingHistoryDelete,
    historyHeader,
    historyDeleteCount,
    historyDeleteMessage,
    historyDeleteLabel,
    archive,
    requestClear,
    confirmClear,
    cancelClear,
    removeOne,
    requestDeleteSelected,
    confirmDeleteSelected,
    cancelDelete,
    previewHistoryItem,
    openHistoryItem,
  }
}
