import { onMounted } from 'vue'

import { api } from '../api.ts'
import type { FolderOptionsBinding } from './use-folder-options.ts'
import type { StatusBinding } from './use-status.ts'

export interface BootstrapDeps {
  options: Pick<FolderOptionsBinding, 'path' | 'logFile'>
  refresh: () => Promise<void>
  status: Pick<StatusBinding, 'reportError'>
}

export interface BootstrapBinding {
  start: () => Promise<void>
}

/**
 * Loads the backend defaults once on mount, then runs the immediate refresh.
 * Assigning path/log intentionally leaves the existing watcher-triggered
 * debounced refresh in place.
 */
export function useBootstrap(deps: BootstrapDeps): BootstrapBinding {
  async function start(): Promise<void> {
    try {
      const defaults = await api.defaults()
      deps.options.path.value = defaults.path
      deps.options.logFile.value = defaults.log_file
    } catch (error) {
      deps.status.reportError(error)
    }
    await deps.refresh()
  }

  onMounted(() => {
    void start()
  })

  return { start }
}
