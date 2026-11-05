import { computed, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useWorkspaceState } from '../../../src/state/use-workspace-state.ts'
import type { FilteredStateResponse } from '../../../src/types.ts'
import {
  deferred,
  filteredStateResponse,
  flushPromises,
  mountHost,
} from '../test-helpers.ts'

function setup() {
  const path = ref('')
  const logFile = ref('')
  const includeHidden = ref(false)
  const mode = ref<'all' | 'files' | 'dirs'>('all')
  const excludedTypes = ref<string[]>([])
  const excludedEntries = ref<string[]>([])
  const folderFlags = computed(() => ({
    include_hidden: includeHidden.value,
    files_only: mode.value === 'files',
    dirs_only: mode.value === 'dirs',
  }))
  const filterExclusions = computed(() => ({
    excluded_types: [...excludedTypes.value],
    excluded_entries: [...excludedEntries.value],
  }))
  const reportError = vi.fn()
  const onPathChange = vi.fn()
  const onLogChange = vi.fn()
  const onState = vi.fn()

  const { result, wrapper } = mountHost(() =>
    useWorkspaceState({
      path,
      logFile,
      folderFlags,
      filterExclusions,
      status: { reportError },
      onPathChange,
      onLogChange,
      onState,
    }),
  )

  return {
    path,
    logFile,
    includeHidden,
    mode,
    excludedTypes,
    excludedEntries,
    reportError,
    onPathChange,
    onLogChange,
    onState,
    result,
    wrapper,
  }
}

describe('useWorkspaceState', () => {
  it('clears state without a request when the trimmed path is blank', async () => {
    const { result, path, onState } = setup()
    const stateFiltered = vi.spyOn(api, 'stateFiltered')
    result.state.value = filteredStateResponse({ remaining: ['alpha.txt'] })

    path.value = '   '
    await result.refresh()

    expect(result.state.value).toBeNull()
    expect(stateFiltered).not.toHaveBeenCalled()
    expect(onState).toHaveBeenLastCalledWith(null)
  })

  it('replaces state with the filtered response, merging flags and exclusions', async () => {
    const { result, path, logFile, includeHidden, mode, excludedTypes, excludedEntries, onState } =
      setup()
    const response = filteredStateResponse({
      remaining: ['alpha.txt'],
      remaining_total: 1,
    })
    const stateFiltered = vi
      .spyOn(api, 'stateFiltered')
      .mockResolvedValue(response)

    path.value = '/tmp/choosier'
    logFile.value = '/tmp/choosier/custom.jsonl'
    includeHidden.value = true
    mode.value = 'files'
    excludedTypes.value = ['file:.txt']
    excludedEntries.value = ['notes.md']
    await result.refresh()

    expect(stateFiltered).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
      include_hidden: true,
      files_only: true,
      dirs_only: false,
      excluded_types: ['file:.txt'],
      excluded_entries: ['notes.md'],
    })
    expect(result.state.value).toEqual(response)
    expect(onState).toHaveBeenCalledWith(response)
  })

  it('never calls the frozen GET state route', async () => {
    const { result, path } = setup()
    const state = vi.spyOn(api, 'state')
    vi.spyOn(api, 'stateFiltered').mockResolvedValue(filteredStateResponse())

    path.value = '/tmp/choosier'
    await result.refresh()

    expect(state).not.toHaveBeenCalled()
  })

  it('reports a failure through the shared status path and keeps prior state', async () => {
    const { result, path, reportError } = setup()
    const previous = filteredStateResponse({ remaining: ['alpha.txt'] })
    result.state.value = previous
    const failure = new Error('state failed')
    vi.spyOn(api, 'stateFiltered').mockRejectedValue(failure)

    path.value = '/tmp/choosier'
    await result.refresh()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(result.state.value).toEqual(previous)
  })

  it('discards an out-of-order response and only publishes the newest one', async () => {
    vi.useFakeTimers()
    const first = deferred<FilteredStateResponse>()
    const second = deferred<FilteredStateResponse>()
    vi.spyOn(api, 'stateFiltered')
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const { result, path, logFile, onState, wrapper } = setup()

    path.value = '/tmp/choosier'
    await nextTick()
    const firstRefresh = result.refresh()
    await flushPromises()

    logFile.value = 'custom.jsonl'
    await nextTick()
    const secondRefresh = result.refresh()
    await flushPromises()

    second.resolve(filteredStateResponse({ remaining: ['new.txt'] }))
    await secondRefresh
    first.resolve(filteredStateResponse({ remaining: ['old.txt'] }))
    await firstRefresh

    expect(result.state.value?.remaining).toEqual(['new.txt'])
    expect(onState).toHaveBeenLastCalledWith(
      expect.objectContaining({ remaining: ['new.txt'] }),
    )

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('ignores a stale failure instead of reporting it', async () => {
    vi.useFakeTimers()
    const first = deferred<FilteredStateResponse>()
    const second = deferred<FilteredStateResponse>()
    vi.spyOn(api, 'stateFiltered')
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const { result, path, logFile, reportError, wrapper } = setup()

    path.value = '/tmp/choosier'
    await nextTick()
    const firstRefresh = result.refresh()
    await flushPromises()

    logFile.value = 'custom.jsonl'
    await nextTick()
    const secondRefresh = result.refresh()
    await flushPromises()

    second.resolve(filteredStateResponse({ remaining: ['new.txt'] }))
    await secondRefresh
    first.reject(new Error('old failure'))
    await firstRefresh

    expect(reportError).not.toHaveBeenCalled()
    expect(result.state.value?.remaining).toEqual(['new.txt'])

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('debounces path, log, hidden, mode, and exclusion changes by 250ms', async () => {
    vi.useFakeTimers()
    const { result, path, logFile, includeHidden, mode, excludedTypes, wrapper } =
      setup()
    vi.spyOn(api, 'stateFiltered').mockResolvedValue(filteredStateResponse())

    path.value = '/tmp/choosier'
    await nextTick()
    logFile.value = 'custom.jsonl'
    await nextTick()
    includeHidden.value = true
    await nextTick()
    mode.value = 'dirs'
    await nextTick()
    excludedTypes.value = ['file:.txt']
    await nextTick()

    await vi.advanceTimersByTimeAsync(249)
    expect(api.stateFiltered).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(api.stateFiltered).toHaveBeenCalledTimes(1)
    expect(api.stateFiltered).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: 'custom.jsonl',
      include_hidden: true,
      files_only: false,
      dirs_only: true,
      excluded_types: ['file:.txt'],
      excluded_entries: [],
    })

    wrapper.unmount()
    vi.useRealTimers()
  })

  it('notifies path and log changes without firing the other callback', async () => {
    const { path, logFile, onPathChange, onLogChange } = setup()

    path.value = '/tmp/choosier'
    await nextTick()
    expect(onPathChange).toHaveBeenCalledTimes(1)
    expect(onLogChange).not.toHaveBeenCalled()

    logFile.value = 'custom.jsonl'
    await nextTick()
    expect(onPathChange).toHaveBeenCalledTimes(1)
    expect(onLogChange).toHaveBeenCalledTimes(1)
  })

  it('clears the pending debounce on unmount', async () => {
    vi.useFakeTimers()
    const { result, path, wrapper } = setup()
    vi.spyOn(api, 'stateFiltered').mockResolvedValue(filteredStateResponse())

    path.value = '/tmp/choosier'
    await nextTick()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(250)

    expect(api.stateFiltered).not.toHaveBeenCalled()
    expect(result.state.value).toBeNull()
    vi.useRealTimers()
  })
})
