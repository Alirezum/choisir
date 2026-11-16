import { ref, type Ref } from 'vue'

import { api } from '../api.ts'
import type { FilterBinding } from './use-filters.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { StatusBinding } from './use-status.ts'
import type { SkipBinding } from './use-skip.ts'
import type { UndoBinding } from './use-undo.ts'

export interface PickerDeps {
  options: FolderOptionsBinding
  choice: Pick<ChoiceBinding, 'choice' | 'setPicked'>
  status: Pick<StatusBinding, 'setStatus' | 'reportError'>
  refresh: () => Promise<void>
  refreshPathMemory: () => Promise<void>
  pathInput: Ref<HTMLInputElement | null>
  filterExclusions: Pick<FilterBinding, 'exclusions' | 'revision'>
  undo: Pick<UndoBinding, 'setReceipt' | 'clear'>
  skips?: Pick<SkipBinding, 'names' | 'remove' | 'skipping'>
}

export interface PickerBinding {
  pick: () => Promise<void>
  picking: Ref<boolean>
  openEntry: (entry: string) => Promise<void>
  openCurrent: () => Promise<void>
}

/**
 * Owns pick validation, the pick request and its outcomes, and opening the
 * current choice. All visible text is produced here exactly as it was before
 * the refactor.
 */
export function usePicker(deps: PickerDeps): PickerBinding {
  const { options, choice, status } = deps
  const picking = ref(false)

  async function pick(): Promise<void> {
    deps.undo.clear()
    if (deps.skips?.skipping.value) {
      status.setStatus('Wait for the skip action to finish.')
      return
    }
    if (options.path.value.trim() === '') {
      status.setStatus('Enter a folder path.')
      deps.pathInput.value?.focus()
      return
    }

    const rawSeed = options.seed.value.trim()
    let seedValue: number | null = null
    if (rawSeed !== '') {
      seedValue = Number(rawSeed)
      if (!Number.isInteger(seedValue)) {
        status.setStatus('Seed must be a whole number.')
        return
      }
    }

    const revisionAtStart = deps.filterExclusions.revision.value
    const pathAtStart = options.path.value
    picking.value = true
    try {
      const result = await api.pick({
        path: options.path.value,
        log_file: options.logFile.value === '' ? null : options.logFile.value,
        seed: seedValue,
        dry_run: options.dryRun.value,
        ...options.folderFlags.value,
        ...deps.filterExclusions.exclusions.value,
        skipped_entries: [...(deps.skips?.names.value ?? [])],
      })
      if (
        deps.filterExclusions.revision.value !== revisionAtStart ||
        options.path.value !== pathAtStart
      ) {
        return
      }
      if (result.status === 'invalid_path') {
        status.setStatus("That folder doesn't exist.")
      } else if (result.status === 'empty') {
        status.setStatus('That folder has nothing to pick.')
      } else if (result.status === 'exhausted') {
        status.setStatus(
          'All items have been picked. Clear or archive history to start over.',
        )
      } else if (result.status === 'filtered_empty') {
        status.setStatus(
          'Filters exclude every entry. Adjust them in Options or clear all filters.',
        )
      } else if (result.status === 'filtered_exhausted') {
        status.setStatus(
          'All entries matching the filters have been picked. Clear filters or reset history to pick more.',
        )
      } else if (result.status === 'all_skipped') {
        status.setStatus(
          'Every available item is skipped. Restore skipped items to pick again.',
        )
      } else {
        deps.undo.setReceipt(result.undo ?? null)
        const item = result.item ?? ''
        deps.skips?.remove(item)
        choice.setPicked({
          item,
          path: options.entryPath(item),
          preview: result.preview,
        })
        const pickedStatus = result.logged
          ? `Picked ${item}.`
          : `Picked ${item}. Dry run, so it wasn't logged.`
        await deps.refreshPathMemory()
        status.setStatus(
          result.path_memory_notice
            ? `${pickedStatus} ${result.path_memory_notice}`
            : pickedStatus,
        )
      }
    } catch (error) {
      status.reportError(error)
    } finally {
      picking.value = false
      await deps.refresh()
    }
  }

  async function openEntry(entry: string): Promise<void> {
    try {
      const result = await api.open(entry)
      status.setStatus(`Opened ${result.opened}.`)
    } catch (error) {
      status.reportError(error)
    }
  }

  async function openCurrent(): Promise<void> {
    if (choice.choice.value === null) {
      status.setStatus('Pick something first.')
      return
    }
    await openEntry(choice.choice.value.path)
  }

  return { pick, picking, openEntry, openCurrent }
}
