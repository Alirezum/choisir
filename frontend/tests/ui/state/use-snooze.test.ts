import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useChoice } from '../../../src/state/use-choice.ts'
import { useFolderOptions } from '../../../src/state/use-folder-options.ts'
import { useSkip } from '../../../src/state/use-skip.ts'
import { useSnooze } from '../../../src/state/use-snooze.ts'
import { useUndo } from '../../../src/state/use-undo.ts'
import type { UndoHistoryResponse, UndoReceipt } from '../../../src/types.ts'
import { deferred, flushPromises, mountHost } from '../test-helpers.ts'

const receipt = (item = 'alpha.txt'): UndoReceipt => ({
  item,
  entry: `{"ts": "2026-11-17T10:00:00+00:00", "item": ${JSON.stringify(item)}}`,
  digest: 'a'.repeat(64),
})

const undoResponse = (
  overrides: Partial<UndoHistoryResponse> = {},
): UndoHistoryResponse => ({
  log_file: '/tmp/choosier/.choosier.jsonl',
  status: 'undone',
  item: 'alpha.txt',
  removed: true,
  ...overrides,
})

function setup(item = 'alpha.txt', current = item) {
  const options = useFolderOptions()
  options.path.value = '/tmp/choosier'
  const choice = useChoice()
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const refresh = vi.fn(async () => {})
  let now = 0

  const { result, wrapper } = mountHost(() => {
    const undo = useUndo({
      options,
      choice,
      status: { setStatus, reportError },
      refresh,
    })
    const skips = useSkip({
      status: { setStatus },
      refresh,
      isRemaining: () => false,
      now: () => now,
    })
    const snooze = useSnooze({
      options,
      choice,
      status: { setStatus, reportError },
      undo,
      skips,
      refresh,
    })
    return { undo, skips, snooze }
  })

  const browse = vi.spyOn(api, 'browse').mockResolvedValue({
    path: '/tmp/choosier',
    parent: '/tmp',
    entries: [{ name: item, is_dir: false }],
  })

  return {
    options,
    choice,
    setStatus,
    reportError,
    refresh,
    browse,
    setNow: (value: number) => {
      now = value
    },
    result,
    wrapper,
  }
}

function install(item = 'alpha.txt', current = item) {
  const harness = setup(item, current)
  harness.result.undo.setReceipt(receipt(item))
  harness.choice.setPicked({
    item: current,
    path: `/tmp/choosier/${current}`,
    preview: null,
  })
  return harness
}

describe('useSnooze', () => {
  it('starts unavailable with the nothing-to-snooze label', () => {
    const { result, wrapper } = setup()

    expect(result.snooze.canSnooze.value).toBe(false)
    expect(result.snooze.snoozeLabel.value).toBe(
      'Snooze last pick (nothing to snooze)',
    )
    expect(result.snooze.snoozing.value).toBe(false)

    wrapper.unmount()
  })

  it('exposes the receipt item in the label and availability', () => {
    const { result, wrapper } = install('alpha.txt')

    expect(result.snooze.canSnooze.value).toBe(true)
    expect(result.snooze.snoozeLabel.value).toBe('Snooze last pick: alpha.txt')

    wrapper.unmount()
  })

  it('removes the pick, adds one skip, reports success, and refreshes once', async () => {
    const {
      options,
      result,
      setStatus,
      refresh,
      wrapper,
    } = install()
    options.logFile.value = ''
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockResolvedValue(undoResponse())

    await result.snooze.snooze()

    expect(undoHistory).toHaveBeenCalledTimes(1)
    expect(undoHistory).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: null,
      receipt: receipt(),
    })
    expect(result.skips.names.value).toEqual(['alpha.txt'])
    expect(result.skips.records.value).toEqual([
      { name: 'alpha.txt', expiresAt: 600_000 },
    ])
    expect(setStatus).toHaveBeenCalledWith(
      'Snoozed alpha.txt. Its pick was removed; it returns in ten minutes or when this session ends.',
    )
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(result.undo.receipt.value).toBeNull()
    expect(result.snooze.canSnooze.value).toBe(false)
    expect(result.snooze.snoozing.value).toBe(false)

    wrapper.unmount()
  })

  it('sends the custom log value with the captured receipt', async () => {
    const { options, result, wrapper } = install()
    options.logFile.value = '/tmp/choosier/custom.jsonl'
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockResolvedValue(undoResponse())

    await result.snooze.snooze()

    expect(undoHistory).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
      receipt: receipt(),
    })

    wrapper.unmount()
  })

  it.each([
    ['no receipt', false, true],
    ['a different current choice', true, false],
  ])(
    'sets Nothing to snooze. for %s without an API call, skip, or refresh',
    async (_name, installReceipt, matchingChoice) => {
      const { result, choice, setStatus, refresh, wrapper } = setup()
      if (installReceipt) result.undo.setReceipt(receipt())
      choice.setPicked({
        item: matchingChoice
          ? (result.undo.receipt.value?.item ?? 'alpha.txt')
          : 'beta.txt',
        path: '/tmp/choosier/beta.txt',
        preview: null,
      })
      const undoHistory = vi.spyOn(api, 'undoHistory')

      await result.snooze.snooze()

      expect(setStatus).toHaveBeenCalledWith('Nothing to snooze.')
      expect(undoHistory).not.toHaveBeenCalled()
      expect(result.skips.names.value).toEqual([])
      expect(refresh).not.toHaveBeenCalled()

      wrapper.unmount()
    },
  )

  it.each([
    ['changed', 'Could not snooze alpha.txt: history changed.'],
    ['nothing_to_undo', 'Could not snooze alpha.txt: history is empty.'],
  ] as const)(
    'sets the %s message without a skip and refreshes once',
    async (status, message) => {
      const { result, setStatus, refresh, wrapper } = install()
      vi.spyOn(api, 'undoHistory').mockResolvedValue(
        undoResponse({ status, removed: status === 'undone' }),
      )

      await result.snooze.snooze()

      expect(setStatus).toHaveBeenCalledWith(message)
      expect(result.skips.names.value).toEqual([])
      expect(refresh).toHaveBeenCalledTimes(1)
      expect(result.undo.receipt.value).toBeNull()
      expect(result.snooze.canSnooze.value).toBe(false)

      wrapper.unmount()
    },
  )

  it('reports a rejected request, keeps the receipt, and adds no skip', async () => {
    const { result, setStatus, reportError, refresh, wrapper } = install()
    const failure = new Error('snooze failed')
    vi.spyOn(api, 'undoHistory').mockRejectedValue(failure)

    await result.snooze.snooze()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(setStatus).not.toHaveBeenCalled()
    expect(result.undo.receipt.value).toEqual(receipt())
    expect(result.snooze.canSnooze.value).toBe(true)
    expect(result.skips.names.value).toEqual([])
    expect(refresh).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('refuses a second call while the first request is pending', async () => {
    const { result, setStatus, wrapper } = install()
    const pending = deferred<UndoHistoryResponse>()
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockReturnValue(pending.promise)

    const first = result.snooze.snooze()
    await flushPromises()
    expect(result.snooze.snoozing.value).toBe(true)

    await result.snooze.snooze()
    expect(setStatus).toHaveBeenCalledWith(
      'Wait for the current action to finish.',
    )
    expect(undoHistory).toHaveBeenCalledTimes(1)

    pending.resolve(undoResponse())
    await first
    expect(result.skips.names.value).toEqual(['alpha.txt'])
    expect(result.snooze.snoozing.value).toBe(false)

    wrapper.unmount()
  })

  it('handles a spaced and Unicode item name', async () => {
    const item = 'café notes ☕.txt'
    const { result, setStatus, wrapper } = install(item)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(
      undoResponse({ item, removed: true }),
    )

    await result.snooze.snooze()

    expect(result.skips.names.value).toEqual([item])
    expect(setStatus).toHaveBeenCalledWith(
      `Snoozed ${item}. Its pick was removed; it returns in ten minutes or when this session ends.`,
    )

    wrapper.unmount()
  })

  it.each(['undoing', 'skipping'] as const)(
    'refuses while %s without an API call, skip, or refresh',
    async (busy) => {
      const { result, setStatus, refresh, wrapper } = install()
      const undoHistory = vi.spyOn(api, 'undoHistory')
      result.undo.undoing.value = busy === 'undoing'
      result.skips.skipping.value = busy === 'skipping'

      expect(result.snooze.canSnooze.value).toBe(false)
      await result.snooze.snooze()

      expect(setStatus).toHaveBeenCalledWith(
        'Wait for the current action to finish.',
      )
      expect(undoHistory).not.toHaveBeenCalled()
      expect(result.skips.names.value).toEqual([])
      expect(refresh).not.toHaveBeenCalled()
      expect(result.undo.receipt.value).toEqual(receipt())

      wrapper.unmount()
    },
  )

  it('leaves Undo and Snooze unavailable after success until a later pick', async () => {
    const { result, choice, wrapper } = install()
    vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())

    await result.snooze.snooze()

    expect(result.snooze.canSnooze.value).toBe(false)
    expect(result.undo.canUndo.value).toBe(false)
    expect(result.undo.receipt.value).toBeNull()

    result.undo.setReceipt(receipt('beta.txt'))
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })

    expect(result.snooze.canSnooze.value).toBe(true)
    expect(result.undo.canUndo.value).toBe(true)
    expect(result.snooze.snoozeLabel.value).toBe(
      'Snooze last pick: beta.txt',
    )
    expect(result.undo.undoLabel.value).toBe('Undo last pick: beta.txt')

    wrapper.unmount()
  })

  it('leaves a newer choice untouched when it replaces the snoozed one in flight', async () => {
    const { result, choice, wrapper } = install()
    const pending = deferred<UndoHistoryResponse>()
    vi.spyOn(api, 'undoHistory').mockReturnValue(pending.promise)

    const first = result.snooze.snooze()
    await flushPromises()
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    pending.resolve(undoResponse())
    await first

    expect(result.undo.receipt.value).toBeNull()
    expect(choice.choice.value?.item).toBe('beta.txt')
    expect(result.skips.names.value).toEqual(['alpha.txt'])
    expect(result.snooze.canSnooze.value).toBe(false)

    wrapper.unmount()
  })

  it('never recreates the receipt when the skip is restored', async () => {
    const { result, wrapper } = install()
    vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())
    await result.snooze.snooze()

    await result.skips.restore('alpha.txt')

    expect(result.skips.names.value).toEqual([])
    expect(result.undo.receipt.value).toBeNull()
    expect(result.undo.canUndo.value).toBe(false)
    expect(result.snooze.canSnooze.value).toBe(false)

    wrapper.unmount()
  })

  it('never recreates the receipt when the skip expires', async () => {
    vi.useFakeTimers()
    try {
      const { result, setNow, wrapper } = install()
      vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())
      await result.snooze.snooze()

      setNow(600_000)
      vi.advanceTimersByTime(1000)

      expect(result.skips.names.value).toEqual([])
      expect(result.undo.receipt.value).toBeNull()
      expect(result.undo.canUndo.value).toBe(false)
      expect(result.snooze.canSnooze.value).toBe(false)

      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('keeps Undo available for the receipt when history previews a different item', async () => {
    const { result, choice, setStatus, refresh, wrapper } = install()
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    const undoHistory = vi.spyOn(api, 'undoHistory')

    expect(result.undo.canUndo.value).toBe(true)
    expect(result.undo.undoLabel.value).toBe('Undo last pick: alpha.txt')
    expect(result.snooze.canSnooze.value).toBe(false)
    expect(result.snooze.snoozeLabel.value).toBe(
      'Snooze last pick: alpha.txt',
    )

    await result.snooze.snooze()

    expect(setStatus).toHaveBeenCalledWith('Nothing to snooze.')
    expect(undoHistory).not.toHaveBeenCalled()
    expect(result.skips.names.value).toEqual([])
    expect(refresh).not.toHaveBeenCalled()
    expect(choice.choice.value?.item).toBe('beta.txt')
    expect(result.undo.receipt.value).toEqual(receipt())

    wrapper.unmount()
  })

  it('refuses when the item has been deleted or renamed before the undo', async () => {
    const { result, setStatus, refresh, browse, wrapper } = install()
    browse.mockResolvedValue({
      path: '/tmp/choosier',
      parent: '/tmp',
      entries: [{ name: 'renamed.txt', is_dir: false }],
    })
    const undoHistory = vi.spyOn(api, 'undoHistory')

    await result.snooze.snooze()

    expect(browse).toHaveBeenCalledWith('/tmp/choosier')
    expect(undoHistory).not.toHaveBeenCalled()
    expect(setStatus).toHaveBeenCalledWith(
      'Could not snooze alpha.txt: it is no longer available.',
    )
    expect(result.skips.names.value).toEqual([])
    expect(result.undo.receipt.value).toEqual(receipt())
    expect(refresh).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('reports a browse failure and keeps the receipt without refreshing', async () => {
    const { result, reportError, refresh, browse, wrapper } = install()
    const failure = new Error('browse failed')
    browse.mockRejectedValue(failure)
    const undoHistory = vi.spyOn(api, 'undoHistory')

    await result.snooze.snooze()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(undoHistory).not.toHaveBeenCalled()
    expect(result.skips.names.value).toEqual([])
    expect(result.undo.receipt.value).toEqual(receipt())
    expect(refresh).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it.each([
    ['path', (options: ReturnType<typeof useFolderOptions>) => {
      options.path.value = '/tmp/choosier/next'
    }],
    ['log', (options: ReturnType<typeof useFolderOptions>) => {
      options.logFile.value = '/tmp/choosier/custom.jsonl'
    }],
  ])(
    'refuses when the %s changes while the browse preflight is pending',
    async (_scope, change) => {
      const { options, result, setStatus, refresh, browse, wrapper } =
        install()
      const pending = deferred<Awaited<ReturnType<typeof api.browse>>>()
      browse.mockReturnValue(pending.promise)
      const undoHistory = vi.spyOn(api, 'undoHistory')

      const run = result.snooze.snooze()
      await flushPromises()
      change(options)
      pending.resolve({
        path: '/tmp/choosier',
        parent: '/tmp',
        entries: [{ name: 'alpha.txt', is_dir: false }],
      })
      await run

      expect(setStatus).toHaveBeenCalledWith(
        'Could not snooze alpha.txt: the folder or log file changed.',
      )
      expect(undoHistory).not.toHaveBeenCalled()
      expect(result.skips.names.value).toEqual([])
      expect(refresh).not.toHaveBeenCalled()

      wrapper.unmount()
    },
  )

  it('refuses when a newer receipt replaces the captured one during the preflight', async () => {
    const { result, setStatus, refresh, browse, wrapper } = install()
    const pending = deferred<Awaited<ReturnType<typeof api.browse>>>()
    browse.mockReturnValue(pending.promise)
    const undoHistory = vi.spyOn(api, 'undoHistory')

    const run = result.snooze.snooze()
    await flushPromises()
    result.undo.setReceipt(receipt('beta.txt'))
    pending.resolve({
      path: '/tmp/choosier',
      parent: '/tmp',
      entries: [{ name: 'alpha.txt', is_dir: false }],
    })
    await run

    expect(setStatus).toHaveBeenCalledWith(
      'Could not snooze alpha.txt: history changed.',
    )
    expect(undoHistory).not.toHaveBeenCalled()
    expect(result.skips.names.value).toEqual([])
    expect(result.undo.receipt.value).toEqual(receipt('beta.txt'))
    expect(refresh).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it.each([
    ['path', (options: ReturnType<typeof useFolderOptions>) => {
      options.path.value = '/tmp/choosier/next'
    }],
    ['log', (options: ReturnType<typeof useFolderOptions>) => {
      options.logFile.value = '/tmp/choosier/custom.jsonl'
    }],
  ])(
    'keeps the history removal but adds no skip when the %s changes during the undo',
    async (_scope, change) => {
      const { options, result, setStatus, refresh, wrapper } = install()
      const pending = deferred<UndoHistoryResponse>()
      const undoHistory = vi
        .spyOn(api, 'undoHistory')
        .mockReturnValue(pending.promise)

      const run = result.snooze.snooze()
      await flushPromises()
      change(options)
      pending.resolve(undoResponse())
      await run

      expect(undoHistory).toHaveBeenCalledTimes(1)
      expect(setStatus).toHaveBeenCalledWith(
        'Removed the pick of alpha.txt. The folder or log file changed before it could be skipped.',
      )
      expect(result.skips.names.value).toEqual([])
      expect(result.undo.receipt.value).toBeNull()
      expect(refresh).toHaveBeenCalledTimes(1)

      wrapper.unmount()
    },
  )

  it('issues one undo request and one skip for overlapping calls', async () => {
    const { result, setStatus, wrapper } = install()
    const pending = deferred<UndoHistoryResponse>()
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockReturnValue(pending.promise)

    const first = result.snooze.snooze()
    await flushPromises()
    const second = result.snooze.snooze()
    await flushPromises()

    expect(setStatus).toHaveBeenCalledWith(
      'Wait for the current action to finish.',
    )

    pending.resolve(undoResponse())
    await Promise.all([first, second])

    expect(undoHistory).toHaveBeenCalledTimes(1)
    expect(result.skips.names.value).toEqual(['alpha.txt'])

    wrapper.unmount()
  })
})
