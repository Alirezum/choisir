import { describe, expect, it, vi } from 'vitest'

import { mountHost } from '../test-helpers.ts'
import {
  SKIP_COOLDOWN_MS,
  useSkip,
  type SkipBinding,
} from '../../../src/state/use-skip.ts'

interface Harness {
  result: SkipBinding
  setStatus: ReturnType<typeof vi.fn>
  refresh: ReturnType<typeof vi.fn>
  remaining: Set<string>
  setNow: (value: number) => void
  unmount: () => void
}

function setup(name = 'alpha.txt'): Harness {
  let current = 0
  const setStatus = vi.fn()
  const refresh = vi.fn(async () => {})
  const remaining = new Set<string>([name])

  const { result, wrapper } = mountHost(() =>
    useSkip({
      status: { setStatus },
      refresh,
      isRemaining: (item) => remaining.has(item),
      now: () => current,
    }),
  )

  return {
    result,
    setStatus,
    refresh,
    remaining,
    setNow: (value) => {
      current = value
    },
    unmount: () => wrapper.unmount(),
  }
}

describe('useSkip', () => {
  it('starts with no records and exposes the cooldown', () => {
    const { result, unmount } = setup()
    expect(result.records.value).toEqual([])
    expect(result.names.value).toEqual([])
    expect(result.skipping.value).toBe(false)
    expect(SKIP_COOLDOWN_MS).toBe(600_000)
    unmount()
  })

  it('records one skip, announces it, and refreshes', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')

    expect(harness.result.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 600_000 },
    ])
    expect(harness.result.names.value).toEqual(['alpha.txt'])
    expect(harness.setStatus).toHaveBeenCalledWith(
      'Skipped alpha.txt. It returns in ten minutes or when this session ends.',
    )
    expect(harness.refresh).toHaveBeenCalledTimes(1)
    harness.unmount()
  })

  it('replaces an existing record instead of duplicating it', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.setNow(1000)
    await harness.result.skip('alpha.txt')

    expect(harness.result.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 601_000 },
    ])
    harness.unmount()
  })

  it('refuses a name that is not remaining', async () => {
    const harness = setup()
    await harness.result.skip('gone.txt')

    expect(harness.result.records.value).toEqual([])
    expect(harness.setStatus).toHaveBeenCalledWith(
      'Could not skip gone.txt: it is no longer available.',
    )
    expect(harness.refresh).not.toHaveBeenCalled()
    harness.unmount()
  })

  it('removes expired records on the one-second tick', async () => {
    vi.useFakeTimers()
    try {
      const harness = setup()
      await harness.result.skip('alpha.txt')
      expect(harness.result.names.value).toEqual(['alpha.txt'])

      harness.setNow(600_000)
      vi.advanceTimersByTime(1000)

      expect(harness.result.records.value).toEqual([])
      expect(harness.refresh).toHaveBeenCalledTimes(2)
      harness.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('reconciles only the names included in the request snapshot', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.setNow(1000)
    harness.remaining.add('late.txt')
    await harness.result.skip('late.txt')

    harness.result.reconcile(['alpha.txt'], ['alpha.txt'])
    expect(harness.result.names.value).toEqual(['alpha.txt', 'late.txt'])

    harness.result.reconcile(['alpha.txt'], [])
    expect(harness.result.names.value).toEqual(['late.txt'])
    harness.unmount()
  })

  it('keeps a present name even when it is no longer remaining', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.remaining.delete('alpha.txt')

    harness.result.reconcile(['alpha.txt'], ['alpha.txt'])
    expect(harness.result.names.value).toEqual(['alpha.txt'])
    harness.unmount()
  })

  it('clears everything on reset without touching history', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.result.reset()

    expect(harness.result.records.value).toEqual([])
    expect(harness.result.names.value).toEqual([])
    harness.unmount()
  })

  it('never writes to browser storage', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const harness = setup()
    await harness.result.skip('alpha.txt')
    expect(setItem).not.toHaveBeenCalled()
    setItem.mockRestore()
    harness.unmount()
  })
})
