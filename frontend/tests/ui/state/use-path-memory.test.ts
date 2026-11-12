import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { usePathMemory } from '../../../src/state/use-path-memory.ts'

function setup() {
  const reportError = vi.fn()
  const memory = usePathMemory({ status: { reportError } })
  return { memory, reportError }
}

describe('usePathMemory', () => {
  it('starts with an empty list and no warning', () => {
    const { memory } = setup()

    expect(memory.recent.value).toEqual([])
    expect(memory.warning.value).toBeNull()
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
})
