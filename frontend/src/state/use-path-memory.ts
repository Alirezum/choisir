import { ref, type Ref } from 'vue'

import { api } from '../api.ts'
import type { StatusBinding } from './use-status.ts'

export interface PathMemoryDeps {
  status: Pick<StatusBinding, 'reportError' | 'setStatus'>
}

export interface PathMemoryBinding {
  recent: Ref<string[]>
  warning: Ref<string | null>
  notice: Ref<string>
  refresh: () => Promise<void>
  remove: (path: string) => Promise<void>
  clear: () => Promise<void>
}

/**
 * The remembered-folder list shared by the options panel. Loading and
 * mutations are best-effort: failures report through the status line and keep
 * whatever the panel already showed. Memory actions never touch the active
 * folder; only `refresh` reads the record.
 */
export function usePathMemory(deps: PathMemoryDeps): PathMemoryBinding {
  const recent = ref<string[]>([])
  const warning = ref<string | null>(null)
  const notice = ref('')

  async function refresh(): Promise<void> {
    try {
      const result = await api.paths()
      recent.value = result.recent
      warning.value = result.warning
    } catch (error) {
      deps.status.reportError(error)
    }
  }

  function feedback(message: string): void {
    notice.value = message
    deps.status.setStatus(message)
  }

  async function remove(path: string): Promise<void> {
    try {
      const result = await api.removePath(path)
      feedback(
        result.removed
          ? `Removed ${result.path} from remembered folders.`
          : `${result.path} is not a remembered folder.`,
      )
      await refresh()
    } catch (error) {
      deps.status.reportError(error)
    }
  }

  async function clear(): Promise<void> {
    try {
      const result = await api.clearPaths()
      feedback(
        result.cleared
          ? 'Cleared all remembered folders.'
          : 'No remembered folders to clear.',
      )
      await refresh()
    } catch (error) {
      deps.status.reportError(error)
    }
  }

  return { recent, warning, notice, refresh, remove, clear }
}
