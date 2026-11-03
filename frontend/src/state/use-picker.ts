import type { Ref } from 'vue'

import { api } from '../api.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { ChoiceBinding } from './use-choice.ts'
import type { StatusBinding } from './use-status.ts'

export interface PickerDeps {
  options: FolderOptionsBinding
  choice: Pick<ChoiceBinding, 'choice' | 'setPicked'>
  status: Pick<StatusBinding, 'setStatus' | 'reportError'>
  refresh: () => Promise<void>
  pathInput: Ref<HTMLInputElement | null>
}

export interface PickerBinding {
  pick: () => Promise<void>
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

  async function pick(): Promise<void> {
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

    try {
      const result = await api.pick({
        path: options.path.value,
        log_file: options.logFile.value === '' ? null : options.logFile.value,
        seed: seedValue,
        dry_run: options.dryRun.value,
        ...options.filters.value,
      })
      if (result.status === 'invalid_path') {
        status.setStatus("That folder doesn't exist.")
      } else if (result.status === 'empty') {
        status.setStatus('That folder has nothing to pick.')
      } else if (result.status === 'exhausted') {
        status.setStatus(
          'All items have been picked. Clear or archive history to start over.',
        )
      } else {
        const item = result.item ?? ''
        choice.setPicked({
          item,
          path: options.entryPath(item),
          preview: result.preview,
        })
        status.setStatus(
          result.logged
            ? `Picked ${item}.`
            : `Picked ${item}. Dry run, so it wasn't logged.`,
        )
      }
    } catch (error) {
      status.reportError(error)
    } finally {
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

  return { pick, openEntry, openCurrent }
}
