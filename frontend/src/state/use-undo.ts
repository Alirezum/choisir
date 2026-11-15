import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { UndoReceipt } from '../types.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { StatusBinding } from './use-status.ts'

export interface UndoDeps {
  options: Pick<FolderOptionsBinding, 'path' | 'logFile'>
  choice: Pick<ChoiceBinding, 'choice' | 'invalidate'>
  status: Pick<StatusBinding, 'setStatus' | 'reportError'>
  refresh: () => Promise<void>
}

export interface UndoBinding {
  receipt: Ref<UndoReceipt | null>
  canUndo: ComputedRef<boolean>
  undoing: Ref<boolean>
  undoLabel: ComputedRef<string>
  setReceipt: (receipt: UndoReceipt | null) => void
  clear: () => void
  undo: () => Promise<void>
}

/**
 * Owns the session-only receipt for the latest logged pick. Undo removes only
 * that exact line; every domain outcome clears the receipt, while a transport
 * or API failure keeps it available for retry.
 */
export function useUndo(deps: UndoDeps): UndoBinding {
  const { options, choice, status } = deps
  const receipt = ref<UndoReceipt | null>(null)
  const undoing = ref(false)

  const canUndo = computed(() => receipt.value !== null)
  const undoLabel = computed(() =>
    receipt.value === null
      ? 'Undo last pick (nothing to undo)'
      : `Undo last pick: ${receipt.value.item}`,
  )

  function setReceipt(next: UndoReceipt | null): void {
    receipt.value = next
  }

  function clear(): void {
    receipt.value = null
  }

  async function undo(): Promise<void> {
    const current = receipt.value
    if (current === null || undoing.value) return
    undoing.value = true
    try {
      const result = await api.undoHistory({
        path: options.path.value,
        log_file: options.logFile.value === '' ? null : options.logFile.value,
        receipt: current,
      })
      if (result.status === 'undone') {
        status.setStatus(`Undid pick of ${result.item}.`)
      } else if (result.status === 'changed') {
        status.setStatus(`Could not undo ${result.item}: history changed.`)
      } else {
        status.setStatus(`Could not undo ${result.item}: history is empty.`)
      }
      receipt.value = null
      if (choice.choice.value?.item === current.item) {
        choice.invalidate()
      }
    } catch (error) {
      status.reportError(error)
    } finally {
      undoing.value = false
      await deps.refresh()
    }
  }

  return {
    receipt,
    canUndo,
    undoing,
    undoLabel,
    setReceipt,
    clear,
    undo,
  }
}
