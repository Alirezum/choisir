import { onUnmounted, ref, watch, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { StateResponse } from '../types.ts'
import type { FilterSelection, Mode } from '../view-models.ts'

export interface WorkspaceStateDeps {
  path: Ref<string>
  logFile: Ref<string>
  includeHidden: Ref<boolean>
  mode: Ref<Mode>
  filters: ComputedRef<FilterSelection>
  status: {
    reportError: (error: unknown) => void
  }
  onPathChange?: () => void
  onLogChange?: () => void
}

export interface WorkspaceStateBinding {
  state: Ref<StateResponse | null>
  refresh: () => Promise<void>
  scheduleRefresh: () => void
}

const REFRESH_DELAY = 250

/**
 * Owns the loaded workspace state, the debounced refresh, and the path/log
 * change notifications. It never decides what a failed request means beyond
 * forwarding it to the shared status unit.
 */
export function useWorkspaceState(
  deps: WorkspaceStateDeps,
): WorkspaceStateBinding {
  const state = ref<StateResponse | null>(null)
  let refreshTimer: number | undefined

  async function refresh(): Promise<void> {
    if (deps.path.value.trim() === '') {
      state.value = null
      return
    }
    try {
      state.value = await api.state({
        path: deps.path.value,
        log_file: deps.logFile.value,
        ...deps.filters.value,
      })
    } catch (error) {
      deps.status.reportError(error)
    }
  }

  function scheduleRefresh(): void {
    window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(() => void refresh(), REFRESH_DELAY)
  }

  watch(
    [deps.path, deps.logFile, deps.includeHidden, deps.mode],
    scheduleRefresh,
  )
  watch(deps.path, () => deps.onPathChange?.())
  watch(deps.logFile, () => deps.onLogChange?.())

  onUnmounted(() => {
    window.clearTimeout(refreshTimer)
  })

  return { state, refresh, scheduleRefresh }
}
