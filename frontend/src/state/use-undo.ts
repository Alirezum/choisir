import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { UndoReceipt } from '../types.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { StatusBinding } from './use-status.ts'

export type UndoOutcome =
  | { kind: 'unavailable' }
  | { kind: 'failed'; error: unknown }
  | { kind: 'undone'; item: string }
  | { kind: 'changed'; item: string }
  | { kind: 'nothing_to_undo'; item: string }

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
  performUndo: () => Promise<UndoOutcome>
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

  /**
   * Attempt the call without choosing Undo's presentation. The receipt is
   * captured once so a newer pick installed mid-flight stays intact.
   */
  async function performUndo(): Promise<UndoOutcome> {
    const current = receipt.value
    if (current === null || undoing.value) return { kind: 'unavailable' }
    undoing.value = true
    try {
      const result = await api.undoHistory({
        path: options.path.value,
        log_file: options.logFile.value === '' ? null : options.logFile.value,
        receipt: current,
      })
      if (result.status === 'undone') {
        consume(current)
        return { kind: 'undone', item: result.item }
      }
      if (result.status === 'changed') {
        consume(current)
        return { kind: 'changed', item: result.item }
      }
      consume(current)
      return { kind: 'nothing_to_undo', item: result.item }
    } catch (error) {
      return { kind: 'failed', error }
    } finally {
      undoing.value = false
    }
  }

  function consume(current: UndoReceipt): void {
    const stillCurrent = receipt.value === current
    if (!stillCurrent) return
    receipt.value = null
    if (choice.choice.value?.item === current.item) choice.invalidate()
  }

  async function undo(): Promise<void> {
    const outcome = await performUndo()
    if (outcome.kind === 'unavailable') return
    if (outcome.kind === 'undone') {
      status.setStatus(`Undid pick of ${outcome.item}.`)
    } else if (outcome.kind === 'changed') {
      status.setStatus(`Could not undo ${outcome.item}: history changed.`)
    } else if (outcome.kind === 'nothing_to_undo') {
      status.setStatus(`Could not undo ${outcome.item}: history is empty.`)
    } else {
      status.reportError(outcome.error)
    }
    await deps.refresh()
  }

  return {
    receipt,
    canUndo,
    undoing,
    undoLabel,
    setReceipt,
    clear,
    performUndo,
    undo,
  }
}
