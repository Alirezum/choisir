import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { SkipBinding } from './use-skip.ts'
import type { StatusBinding } from './use-status.ts'
import type { UndoBinding } from './use-undo.ts'

export interface SnoozeDeps {
  options: Pick<FolderOptionsBinding, 'path' | 'logFile'>
  choice: Pick<ChoiceBinding, 'choice' | 'invalidate'>
  status: Pick<StatusBinding, 'setStatus' | 'reportError'>
  undo: Pick<UndoBinding, 'receipt' | 'performUndo' | 'undoing'>
  skips: Pick<SkipBinding, 'add' | 'skipping'>
  refresh: () => Promise<void>
}

export interface SnoozeBinding {
  canSnooze: ComputedRef<boolean>
  snoozing: Ref<boolean>
  snoozeLabel: ComputedRef<string>
  snooze: () => Promise<void>
}

/**
 * Composes the shipped Undo and skip behaviors: Snooze removes the latest
 * logged pick exactly as Undo does, then defers that same item for the session.
 * A refusal changes neither history nor skips.
 */
export function useSnooze(deps: SnoozeDeps): SnoozeBinding {
  const { options, choice, status, undo, skips } = deps
  const snoozing = ref(false)

  const canSnooze = computed(() => {
    if (snoozing.value || undo.undoing.value || skips.skipping.value) {
      return false
    }
    const receipt = undo.receipt.value
    return receipt !== null && choice.choice.value?.item === receipt.item
  })

  const snoozeLabel = computed(() =>
    undo.receipt.value === null
      ? 'Snooze last pick (nothing to snooze)'
      : `Snooze last pick: ${undo.receipt.value.item}`,
  )

  async function snooze(): Promise<void> {
    if (snoozing.value || undo.undoing.value || skips.skipping.value) {
      status.setStatus('Wait for the current action to finish.')
      return
    }
    const receipt = undo.receipt.value
    if (receipt === null || choice.choice.value?.item !== receipt.item) {
      status.setStatus('Nothing to snooze.')
      return
    }

    const item = receipt.item
    const pathAtStart = options.path.value
    const logAtStart = options.logFile.value
    snoozing.value = true
    try {
      let entries: { name: string }[] = []
      let browseFailed = false
      let browseError: unknown = null
      try {
        entries = (await api.browse(pathAtStart)).entries
      } catch (error) {
        browseFailed = true
        browseError = error
      }
      if (
        options.path.value !== pathAtStart ||
        options.logFile.value !== logAtStart
      ) {
        status.setStatus(
          `Could not snooze ${item}: the folder or log file changed.`,
        )
        return
      }
      if (browseFailed) {
        status.reportError(browseError)
        return
      }
      if (undo.receipt.value !== receipt) {
        status.setStatus(`Could not snooze ${item}: history changed.`)
        return
      }
      if (!entries.some((entry) => entry.name === item)) {
        status.setStatus(
          `Could not snooze ${item}: it is no longer available.`,
        )
        return
      }

      const outcome = await undo.performUndo()
      if (outcome.kind === 'undone') {
        if (
          options.path.value !== pathAtStart ||
          options.logFile.value !== logAtStart
        ) {
          status.setStatus(
            `Removed the pick of ${outcome.item}. The folder or log file changed before it could be skipped.`,
          )
        } else {
          skips.add(outcome.item)
          status.setStatus(
            `Snoozed ${outcome.item}. Its pick was removed; it returns in ten minutes or when this session ends.`,
          )
        }
      } else if (outcome.kind === 'changed' || outcome.kind === 'unavailable') {
        status.setStatus(`Could not snooze ${item}: history changed.`)
      } else if (outcome.kind === 'nothing_to_undo') {
        status.setStatus(`Could not snooze ${item}: history is empty.`)
      } else {
        status.reportError(outcome.error)
      }
      await deps.refresh()
    } finally {
      snoozing.value = false
    }
  }

  return {
    canSnooze,
    snoozing,
    snoozeLabel,
    snooze,
  }
}
