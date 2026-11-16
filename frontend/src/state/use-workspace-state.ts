import {
  computed,
  onUnmounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'

import { api } from '../api.ts'
import type {
  FilteredStateResponse,
  FilterExclusions,
  FolderFlags,
} from '../types.ts'

export interface WorkspaceStateDeps {
  path: Ref<string>
  logFile: Ref<string>
  folderFlags: ComputedRef<FolderFlags>
  filterExclusions: ComputedRef<FilterExclusions>
  skippedEntries?: ComputedRef<readonly string[]>
  status: {
    reportError: (error: unknown) => void
  }
  onPathChange?: () => void
  onLogChange?: () => void
  onState?: (
    response: FilteredStateResponse | null,
    sentSkips: readonly string[],
  ) => void
}

export interface WorkspaceStateBinding {
  state: Ref<FilteredStateResponse | null>
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
  const state = ref<FilteredStateResponse | null>(null)
  const skippedEntries = deps.skippedEntries ?? computed(() => [])
  let refreshTimer: number | undefined
  let requestNumber = 0

  async function refresh(): Promise<void> {
    if (deps.path.value.trim() === '') {
      requestNumber += 1
      state.value = null
      deps.onState?.(null, [])
      return
    }
    const current = ++requestNumber
    const sentSkips = [...skippedEntries.value]
    try {
      const response = await api.stateFiltered({
        path: deps.path.value,
        log_file: deps.logFile.value,
        ...deps.folderFlags.value,
        ...deps.filterExclusions.value,
        skipped_entries: sentSkips,
      })
      if (current !== requestNumber) return
      state.value = response
      deps.onState?.(response, sentSkips)
    } catch (error) {
      if (current !== requestNumber) return
      deps.status.reportError(error)
    }
  }

  function scheduleRefresh(): void {
    window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(() => void refresh(), REFRESH_DELAY)
  }

  watch(
    [deps.path, deps.logFile, deps.folderFlags, deps.filterExclusions],
    scheduleRefresh,
  )
  watch(deps.path, () => deps.onPathChange?.())
  watch(deps.logFile, () => deps.onLogChange?.())

  onUnmounted(() => {
    window.clearTimeout(refreshTimer)
  })

  return { state, refresh, scheduleRefresh }
}
