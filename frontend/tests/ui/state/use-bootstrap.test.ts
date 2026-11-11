import { computed } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useBootstrap } from '../../../src/state/use-bootstrap.ts'
import { useFolderOptions } from '../../../src/state/use-folder-options.ts'
import { useWorkspaceState } from '../../../src/state/use-workspace-state.ts'
import { filteredStateResponse, flushPromises, mountHost } from '../test-helpers.ts'

function setup(
  defaults: () => Promise<{
    path: string
    log_file: string
    path_warning: string | null
  }> = () =>
    Promise.resolve({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
      path_warning: null,
    }),
) {
  const defaultsMock = vi.spyOn(api, 'defaults').mockImplementation(defaults)
  const options = useFolderOptions()
  const refresh = vi.fn(async () => {})
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const { result, wrapper } = mountHost(() =>
    useBootstrap({
      options,
      refresh,
      status: { setStatus, reportError },
    }),
  )
  return { defaultsMock, options, refresh, setStatus, reportError, result, wrapper }
}

describe('useBootstrap', () => {
  it('loads defaults into the folder options and runs the immediate refresh on mount', async () => {
    const { options, refresh, reportError, wrapper } = setup()

    await flushPromises()

    expect(api.defaults).toHaveBeenCalledTimes(1)
    expect(options.path.value).toBe('/tmp/choosier')
    expect(options.logFile.value).toBe('/tmp/choosier/custom.jsonl')
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(reportError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('reports a defaults failure through the shared path and still refreshes', async () => {
    const failure = new Error('defaults failed')
    const { options, refresh, reportError, wrapper } = setup(() =>
      Promise.reject(failure),
    )

    await flushPromises()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(options.path.value).toBe('')
    expect(options.logFile.value).toBe('')
    expect(refresh).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('applies the startup path warning without masking a later refresh failure', async () => {
    const calls: string[] = []
    const defaults = vi.spyOn(api, 'defaults').mockResolvedValue({
      path: '/tmp/choosier',
      log_file: '',
      path_warning: 'Skipped 1 unavailable remembered folder.',
    })
    const options = useFolderOptions()
    const setStatus = vi.fn((message: string) => {
      calls.push(`status:${message}`)
    })
    const reportError = vi.fn(() => {
      calls.push('error')
    })
    const refresh = vi.fn(async () => {
      reportError(new Error('refresh failed'))
    })
    const { wrapper } = mountHost(() =>
      useBootstrap({
        options,
        refresh,
        status: { setStatus, reportError },
      }),
    )

    await flushPromises()

    expect(defaults).toHaveBeenCalledTimes(1)
    expect(setStatus).toHaveBeenCalledWith(
      'Skipped 1 unavailable remembered folder.',
    )
    expect(reportError).toHaveBeenCalledTimes(1)
    expect(calls).toEqual([
      'status:Skipped 1 unavailable remembered folder.',
      'error',
    ])
    wrapper.unmount()
  })

  it('preserves the watcher-triggered debounced refresh after defaults load', async () => {
    vi.useFakeTimers()
    const options = useFolderOptions()
    const reportError = vi.fn()
    vi.spyOn(api, 'stateFiltered').mockResolvedValue(filteredStateResponse())
    const state = useWorkspaceState({
      path: options.path,
      logFile: options.logFile,
      folderFlags: options.folderFlags,
      filterExclusions: computed(() => ({
        excluded_types: [],
        excluded_entries: [],
      })),
      status: { reportError },
    })
    vi.spyOn(api, 'defaults').mockResolvedValue({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
      path_warning: null,
    })
    const { wrapper } = mountHost(() =>
      useBootstrap({
        options,
        refresh: state.refresh,
        status: { reportError },
      }),
    )

    await flushPromises()
    expect(api.stateFiltered).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(250)
    expect(api.stateFiltered).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    vi.useRealTimers()
  })
})
