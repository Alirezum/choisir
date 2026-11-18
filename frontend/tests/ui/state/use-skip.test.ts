import { describe, expect, it, vi } from 'vitest'

import { mountHost } from '../test-helpers.ts'
import {
  SKIP_COOLDOWN_MS,
  formatRemaining,
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


  it('formats a remaining cooldown as m:ss', () => {
    expect(formatRemaining(600_000)).toBe('10:00')
    expect(formatRemaining(599_001)).toBe('10:00')
    expect(formatRemaining(59_000)).toBe('0:59')
    expect(formatRemaining(1_000)).toBe('0:01')
    expect(formatRemaining(0)).toBe('0:00')
    expect(formatRemaining(-5)).toBe('0:00')
  })

  it('sorts skipped rows by expiry and updates their countdown on the tick', async () => {
    vi.useFakeTimers()
    try {
      const harness = setup()
      await harness.result.skip('alpha.txt')
      harness.setNow(30_000)
      harness.remaining.add('beta.txt')
      await harness.result.skip('beta.txt')

      expect(harness.result.skippedRows.value).toEqual([
        { name: 'alpha.txt', returnsIn: '9:30' },
        { name: 'beta.txt', returnsIn: '10:00' },
      ])

      harness.setNow(31_000)
      vi.advanceTimersByTime(1000)
      expect(harness.result.skippedRows.value).toEqual([
        { name: 'alpha.txt', returnsIn: '9:29' },
        { name: 'beta.txt', returnsIn: '9:59' },
      ])
      harness.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('restores one skipped entry and leaves the others', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.setNow(1000)
    harness.remaining.add('beta.txt')
    await harness.result.skip('beta.txt')

    await harness.result.restore('alpha.txt')

    expect(harness.result.names.value).toEqual(['beta.txt'])
    expect(harness.setStatus).toHaveBeenLastCalledWith('Restored alpha.txt.')
    expect(harness.refresh).toHaveBeenCalledTimes(3)
    harness.unmount()
  })

  it('refuses to restore an unknown entry', async () => {
    const harness = setup()

    await harness.result.restore('gone.txt')

    expect(harness.result.records.value).toEqual([])
    expect(harness.setStatus).toHaveBeenCalledWith(
      'Could not restore gone.txt: it is no longer available.',
    )
    expect(harness.refresh).not.toHaveBeenCalled()
    harness.unmount()
  })

  it('restores all skipped entries with the singular message', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')

    await harness.result.restoreAll()

    expect(harness.result.records.value).toEqual([])
    expect(harness.setStatus).toHaveBeenLastCalledWith('Restored 1 skipped item.')
    harness.unmount()
  })

  it('restores all skipped entries with the plural message', async () => {
    const harness = setup()
    await harness.result.skip('alpha.txt')
    harness.setNow(1000)
    harness.remaining.add('beta.txt')
    await harness.result.skip('beta.txt')

    await harness.result.restoreAll()

    expect(harness.result.records.value).toEqual([])
    expect(harness.setStatus).toHaveBeenLastCalledWith(
      'Restored 2 skipped items.',
    )
    harness.unmount()
  })

  it('refuses to restore all when nothing is skipped', async () => {
    const harness = setup()

    await harness.result.restoreAll()

    expect(harness.setStatus).toHaveBeenCalledWith(
      'Could not restore skipped items: nothing is available.',
    )
    expect(harness.refresh).not.toHaveBeenCalled()
    harness.unmount()
  })

  it('never writes to browser storage while restoring', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const harness = setup()
    await harness.result.skip('alpha.txt')
    await harness.result.restore('alpha.txt')
    harness.setNow(1000)
    harness.remaining.add('beta.txt')
    await harness.result.skip('beta.txt')
    await harness.result.restoreAll()
    expect(setItem).not.toHaveBeenCalled()
    setItem.mockRestore()
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

  it('adds a record without announcing, refreshing, or toggling skipping', () => {
    const harness = setup()

    harness.result.add('alpha.txt')

    expect(harness.result.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 600_000 },
    ])
    expect(harness.result.skipping.value).toBe(false)
    expect(harness.setStatus).not.toHaveBeenCalled()
    expect(harness.refresh).not.toHaveBeenCalled()
    harness.unmount()
  })

  it('replaces an existing record and restarts its expiry through add', () => {
    const harness = setup()
    harness.result.add('alpha.txt')
    harness.setNow(1000)

    harness.result.add('alpha.txt')

    expect(harness.result.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 601_000 },
    ])
    harness.unmount()
  })

  it('prunes expired records before adding', () => {
    const harness = setup()
    harness.result.add('expired.txt')
    harness.setNow(600_000)

    harness.result.add('alpha.txt')

    expect(harness.result.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 1_200_000 },
    ])
    harness.unmount()
  })

  it('adds folders, videos, images, spaced, and Unicode names even when not remaining', () => {
    const harness = setup()
    const names = [
      'delta',
      'clip.mp4',
      'preview.png',
      'notes with space.txt',
      'café ☕',
    ]

    for (const name of names) harness.result.add(name)

    expect(harness.result.names.value).toEqual(names)
    expect(harness.setStatus).not.toHaveBeenCalled()
    expect(harness.refresh).not.toHaveBeenCalled()
    expect(harness.result.skipping.value).toBe(false)
    harness.unmount()
  })

  it('adds without touching browser storage or cookies', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const cookieBefore = document.cookie
    const harness = setup()

    harness.result.add('alpha.txt')

    expect(setItem).not.toHaveBeenCalled()
    expect(document.cookie).toBe(cookieBefore)
    setItem.mockRestore()
    harness.unmount()
  })
})
