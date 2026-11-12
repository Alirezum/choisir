import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { usePathMemory } from '../../../src/state/use-path-memory.ts'

function setup() {
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const memory = usePathMemory({ status: { setStatus, reportError } })
  return { memory, setStatus, reportError }
}

describe('usePathMemory', () => {
  it('starts with an empty list, no warning, and no notice', () => {
    const { memory } = setup()

    expect(memory.recent.value).toEqual([])
    expect(memory.warning.value).toBeNull()
    expect(memory.notice.value).toBe('')
  })

  it('loads the recent folders and warning from the API', async () => {
    const { memory } = setup()
    const paths = vi.spyOn(api, 'paths').mockResolvedValue({
      recent: ['/tmp/choosier/alpha', '/tmp/choosier/beta'],
      warning: 'Skipped 1 unavailable remembered folder.',
    })

    await memory.refresh()

    expect(paths).toHaveBeenCalledTimes(1)
    expect(memory.recent.value).toEqual([
      '/tmp/choosier/alpha',
      '/tmp/choosier/beta',
    ])
    expect(memory.warning.value).toBe(
      'Skipped 1 unavailable remembered folder.',
    )
  })

  it('clears the warning when a later load is clean', async () => {
    const { memory } = setup()
    vi.spyOn(api, 'paths')
      .mockResolvedValueOnce({ recent: ['/tmp/a'], warning: 'read failed' })
      .mockResolvedValueOnce({ recent: ['/tmp/a'], warning: null })

    await memory.refresh()
    await memory.refresh()

    expect(memory.warning.value).toBeNull()
  })

  it('keeps the current list and reports a load failure without throwing', async () => {
    const { memory, reportError } = setup()
    vi.spyOn(api, 'paths')
      .mockResolvedValueOnce({ recent: ['/tmp/a'], warning: null })
      .mockRejectedValueOnce(new Error('paths failed'))
    await memory.refresh()

    await expect(memory.refresh()).resolves.toBeUndefined()

    expect(memory.recent.value).toEqual(['/tmp/a'])
    expect(reportError).toHaveBeenCalledTimes(1)
  })

  it('removes one remembered folder and refreshes the list', async () => {
    const { memory, setStatus, reportError } = setup()
    const remove = vi
      .spyOn(api, 'removePath')
      .mockResolvedValue({ path: '/tmp/a', removed: true })
    vi.spyOn(api, 'paths').mockResolvedValue({
      recent: ['/tmp/b'],
      warning: null,
    })

    await memory.remove('/tmp/a')

    expect(remove).toHaveBeenCalledWith('/tmp/a')
    expect(memory.recent.value).toEqual(['/tmp/b'])
    expect(memory.notice.value).toBe(
      'Removed /tmp/a from remembered folders.',
    )
    expect(setStatus).toHaveBeenCalledWith(
      'Removed /tmp/a from remembered folders.',
    )
    expect(reportError).not.toHaveBeenCalled()
  })

  it('treats removing an absent folder as a no-op notice', async () => {
    const { memory, setStatus } = setup()
    vi.spyOn(api, 'removePath').mockResolvedValue({
      path: '/tmp/gone',
      removed: false,
    })
    const paths = vi.spyOn(api, 'paths').mockResolvedValue({
      recent: ['/tmp/a'],
      warning: null,
    })

    await memory.remove('/tmp/gone')

    expect(paths).toHaveBeenCalledTimes(1)
    expect(memory.recent.value).toEqual(['/tmp/a'])
    expect(setStatus).toHaveBeenCalledWith(
      '/tmp/gone is not a remembered folder.',
    )
  })

  it('reports a remove failure through the status binding', async () => {
    const { memory, reportError, setStatus } = setup()
    const failure = new Error('remove failed')
    vi.spyOn(api, 'removePath').mockRejectedValue(failure)
    const paths = vi.spyOn(api, 'paths')

    await expect(memory.remove('/tmp/a')).resolves.toBeUndefined()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(setStatus).not.toHaveBeenCalled()
    expect(paths).not.toHaveBeenCalled()
    expect(memory.notice.value).toBe('')
  })

  it('clears all remembered folders and refreshes the list', async () => {
    const { memory, setStatus } = setup()
    const clear = vi
      .spyOn(api, 'clearPaths')
      .mockResolvedValue({ cleared: true })
    vi.spyOn(api, 'paths').mockResolvedValue({ recent: [], warning: null })

    await memory.clear()

    expect(clear).toHaveBeenCalledTimes(1)
    expect(memory.recent.value).toEqual([])
    expect(setStatus).toHaveBeenCalledWith('Cleared all remembered folders.')
  })

  it('reports an already empty list when clearing', async () => {
    const { memory, setStatus } = setup()
    vi.spyOn(api, 'clearPaths').mockResolvedValue({ cleared: false })
    vi.spyOn(api, 'paths').mockResolvedValue({ recent: [], warning: null })

    await memory.clear()

    expect(setStatus).toHaveBeenCalledWith('No remembered folders to clear.')
  })

  it('reports a clear failure through the status binding', async () => {
    const { memory, reportError } = setup()
    const failure = new Error('clear failed')
    vi.spyOn(api, 'clearPaths').mockRejectedValue(failure)
    vi.spyOn(api, 'paths').mockResolvedValue({
      recent: ['/tmp/a'],
      warning: null,
    })
    await memory.refresh()

    await expect(memory.clear()).resolves.toBeUndefined()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(memory.recent.value).toEqual(['/tmp/a'])
  })
})
