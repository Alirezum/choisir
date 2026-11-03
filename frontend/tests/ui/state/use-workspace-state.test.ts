import { computed, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useWorkspaceState } from '../../../src/state/use-workspace-state.ts'
import type { StateResponse } from '../../../src/types.ts'
import { mountHost } from '../test-helpers.ts'

const stateResponse = (remaining: string[]): StateResponse => ({
  valid_path: true,
  path: '/tmp/choosier',
  log_file: '/tmp/choosier/.choosier.jsonl',
  remaining,
  remaining_total: remaining.length,
  history: [],
  history_total: 0,
})

function setup() {
  const path = ref('')
  const logFile = ref('')
  const includeHidden = ref(false)
  const mode = ref<'all' | 'files' | 'dirs'>('all')
  const filters = computed(() => ({
    include_hidden: includeHidden.value,
    files_only: mode.value === 'files',
    dirs_only: mode.value === 'dirs',
  }))
  const reportError = vi.fn()
  const onPathChange = vi.fn()
  const onLogChange = vi.fn()

  const { result, wrapper } = mountHost(() =>
    useWorkspaceState({
      path,
      logFile,
      includeHidden,
      mode,
      filters,
      status: { reportError },
      onPathChange,
      onLogChange,
    }),
  )

  return {
    path,
    logFile,
    includeHidden,
    mode,
    reportError,
    onPathChange,
    onLogChange,
    result,
    wrapper,
  }
}

describe('useWorkspaceState', () => {
  it('clears state without a request when the trimmed path is blank', async () => {
    const { result, path } = setup()
    const state = vi.spyOn(api, 'state')
    result.state.value = stateResponse(['alpha.txt'])

    path.value = '   '
    await result.refresh()

    expect(result.state.value).toBeNull()
    expect(state).not.toHaveBeenCalled()
  })

  it('replaces state with the response, sending path, log file, and filters', async () => {
    const { result, path, logFile, includeHidden, mode } = setup()
    const response = stateResponse(['alpha.txt'])
    const state = vi.spyOn(api, 'state').mockResolvedValue(response)

    path.value = '/tmp/choosier'
    logFile.value = '/tmp/choosier/custom.jsonl'
    includeHidden.value = true
    mode.value = 'files'
    await result.refresh()

    expect(state).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
      include_hidden: true,
      files_only: true,
      dirs_only: false,
    })
    expect(result.state.value).toEqual(response)
  })

  it('reports a failure through the shared status path and keeps prior state', async () => {
    const { result, path, reportError } = setup()
    const previous = stateResponse(['alpha.txt'])
    result.state.value = previous
    const failure = new Error('state failed')
    vi.spyOn(api, 'state').mockRejectedValue(failure)

    path.value = '/tmp/choosier'
    await result.refresh()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(result.state.value).toEqual(previous)
  })

  it('debounces path, log, hidden, and mode changes by 250ms', async () => {
    vi.useFakeTimers()
    const { result, path, logFile, includeHidden, mode, wrapper } = setup()
    vi.spyOn(api, 'state').mockResolvedValue(stateResponse([]))

    path.value = '/tmp/choosier'
    await nextTick()
    logFile.value = 'custom.jsonl'
    await nextTick()
    includeHidden.value = true
    await nextTick()
    mode.value = 'dirs'
    await nextTick()

    await vi.advanceTimersByTimeAsync(249)
    expect(api.state).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(api.state).toHaveBeenCalledTimes(1)
    expect(api.state).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: 'custom.jsonl',
      include_hidden: true,
      files_only: false,
      dirs_only: true,
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
    vi.spyOn(api, 'state').mockResolvedValue(stateResponse([]))

    path.value = '/tmp/choosier'
    await nextTick()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(250)

    expect(api.state).not.toHaveBeenCalled()
    expect(result.state.value).toBeNull()
    vi.useRealTimers()
  })
})
