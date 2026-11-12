import { ref, type Ref } from 'vue'

import { api } from '../api.ts'
import type { StatusBinding } from './use-status.ts'

export interface PathMemoryDeps {
  status: Pick<StatusBinding, 'reportError'>
}

export interface PathMemoryBinding {
  recent: Ref<string[]>
  warning: Ref<string | null>
  refresh: () => Promise<void>
}

/**
 * The remembered-folder list shared by the options panel. Loading a list is
 * best-effort: a failure reports through the status line and keeps whatever
 * the panel already showed.
 */
export function usePathMemory(deps: PathMemoryDeps): PathMemoryBinding {
  const recent = ref<string[]>([])
  const warning = ref<string | null>(null)

  async function refresh(): Promise<void> {
    try {
      const result = await api.paths()
      recent.value = result.recent
      warning.value = result.warning
    } catch (error) {
      deps.status.reportError(error)
    }
  }

  return { recent, warning, refresh }
}
