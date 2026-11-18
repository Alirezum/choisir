import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useChoice } from '../../../src/state/use-choice.ts'
import { useFolderOptions } from '../../../src/state/use-folder-options.ts'
import { useUndo } from '../../../src/state/use-undo.ts'
import type { UndoHistoryResponse, UndoReceipt } from '../../../src/types.ts'
import { deferred, flushPromises } from '../test-helpers.ts'

const receipt: UndoReceipt = {
  item: 'alpha.txt',
  entry: '{"ts": "2026-11-17T10:00:00+00:00", "item": "alpha.txt"}',
  digest: 'a'.repeat(64),
}

const undoResponse = (
  overrides: Partial<UndoHistoryResponse> = {},
): UndoHistoryResponse => ({
  log_file: '/tmp/choosier/.choosier.jsonl',
  status: 'undone',
  item: 'alpha.txt',
  removed: true,
  ...overrides,
})

function setup() {
  const options = useFolderOptions()
  options.path.value = '/tmp/choosier'
  const choice = useChoice()
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const refresh = vi.fn(async () => {})

  const result = useUndo({
    options,
    choice,
    status: { setStatus, reportError },
    refresh,
  })

  return { options, choice, setStatus, reportError, refresh, result }
}

describe('useUndo', () => {
  it('starts unavailable and sends nothing without a receipt', async () => {
    const { result, refresh } = setup()
    const undoHistory = vi.spyOn(api, 'undoHistory')

    expect(result.canUndo.value).toBe(false)
    expect(result.undoLabel.value).toBe('Undo last pick (nothing to undo)')

    await result.undo()

    expect(undoHistory).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('exposes the receipt, availability, and item-bearing label', () => {
    const { result } = setup()

    result.setReceipt(receipt)

    expect(result.receipt.value).toEqual(receipt)
    expect(result.canUndo.value).toBe(true)
    expect(result.undoLabel.value).toBe('Undo last pick: alpha.txt')

    result.clear()

    expect(result.receipt.value).toBeNull()
    expect(result.canUndo.value).toBe(false)
    expect(result.undoLabel.value).toBe('Undo last pick (nothing to undo)')
  })

  it('undoes the receipt and clears the matching choice and receipt', async () => {
    const { options, choice, result, setStatus, refresh } = setup()
    options.logFile.value = ''
    choice.setPicked({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockResolvedValue(undoResponse())

    await result.undo()

    expect(undoHistory).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: null,
      receipt,
    })
    expect(setStatus).toHaveBeenCalledWith('Undid pick of alpha.txt.')
    expect(choice.choice.value).toBeNull()
    expect(result.receipt.value).toBeNull()
    expect(result.canUndo.value).toBe(false)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('sends an explicit log file when one is set', async () => {
    const { options, result } = setup()
    options.logFile.value = '/tmp/choosier/custom.jsonl'
    result.setReceipt(receipt)
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockResolvedValue(undoResponse())

    await result.undo()

    expect(undoHistory).toHaveBeenCalledWith(
      expect.objectContaining({ log_file: '/tmp/choosier/custom.jsonl' }),
    )
  })

  it('reports changed, clears the receipt, and keeps the log untouched', async () => {
    const { choice, result, setStatus, refresh } = setup()
    choice.setPicked({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(
      undoResponse({ status: 'changed', removed: false }),
    )

    await result.undo()

    expect(setStatus).toHaveBeenCalledWith(
      'Could not undo alpha.txt: history changed.',
    )
    expect(choice.choice.value).toBeNull()
    expect(result.receipt.value).toBeNull()
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('reports nothing to undo, clears the receipt, and keeps the choice', async () => {
    const { choice, result, setStatus } = setup()
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(
      undoResponse({
        status: 'nothing_to_undo',
        item: 'alpha.txt',
        removed: false,
      }),
    )

    await result.undo()

    expect(setStatus).toHaveBeenCalledWith(
      'Could not undo alpha.txt: history is empty.',
    )
    expect(choice.choice.value?.item).toBe('beta.txt')
    expect(result.receipt.value).toBeNull()
  })

  it('clears the choice only when the current item matches the undone item', async () => {
    const { choice, result } = setup()
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())

    await result.undo()

    expect(choice.choice.value?.item).toBe('beta.txt')
  })

  it('retains the receipt and reports the error when the request fails', async () => {
    const { result, reportError, setStatus, refresh } = setup()
    const failure = new Error('undo failed')
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockRejectedValue(failure)

    await result.undo()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(setStatus).not.toHaveBeenCalled()
    expect(result.receipt.value).toEqual(receipt)
    expect(result.canUndo.value).toBe(true)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('ignores a second undo while the first request is pending', async () => {
    const { result } = setup()
    const pending = deferred<UndoHistoryResponse>()
    result.setReceipt(receipt)
    const undoHistory = vi
      .spyOn(api, 'undoHistory')
      .mockReturnValue(pending.promise)

    const first = result.undo()
    await flushPromises()
    expect(result.undoing.value).toBe(true)

    await result.undo()
    expect(undoHistory).toHaveBeenCalledTimes(1)

    pending.resolve(undoResponse())
    await first
    expect(result.undoing.value).toBe(false)
    expect(result.receipt.value).toBeNull()
  })

  it('performUndo returns unavailable without a receipt or while pending', async () => {
    const { result } = setup()
    const undoHistory = vi.spyOn(api, 'undoHistory')

    await expect(result.performUndo()).resolves.toEqual({ kind: 'unavailable' })
    expect(undoHistory).not.toHaveBeenCalled()

    result.setReceipt(receipt)
    const pending = deferred<UndoHistoryResponse>()
    undoHistory.mockReturnValue(pending.promise)

    const first = result.performUndo()
    await flushPromises()
    await expect(result.performUndo()).resolves.toEqual({ kind: 'unavailable' })
    expect(undoHistory).toHaveBeenCalledTimes(1)

    pending.resolve(undoResponse())
    await expect(first).resolves.toEqual({ kind: 'undone', item: 'alpha.txt' })
  })

  it.each(['undone', 'changed', 'nothing_to_undo'] as const)(
    'performUndo returns %s and clears the receipt',
    async (status) => {
      const { result } = setup()
      result.setReceipt(receipt)
      vi.spyOn(api, 'undoHistory').mockResolvedValue(
        undoResponse({ status, removed: status === 'undone' }),
      )

      await expect(result.performUndo()).resolves.toEqual({
        kind: status,
        item: 'alpha.txt',
      })
      expect(result.receipt.value).toBeNull()
    },
  )

  it('performUndo invalidates the matching choice silently', async () => {
    const { choice, result, setStatus, reportError, refresh } = setup()
    choice.setPicked({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())

    await expect(result.performUndo()).resolves.toEqual({
      kind: 'undone',
      item: 'alpha.txt',
    })

    expect(choice.choice.value).toBeNull()
    expect(setStatus).not.toHaveBeenCalled()
    expect(reportError).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('performUndo leaves a different choice and a newer receipt intact', async () => {
    const { choice, result } = setup()
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockResolvedValue(undoResponse())

    await result.performUndo()

    expect(choice.choice.value?.item).toBe('beta.txt')
  })

  it('performUndo reports a failed outcome without presentation or refresh', async () => {
    const { result, setStatus, reportError, refresh } = setup()
    const failure = new Error('undo failed')
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockRejectedValue(failure)

    await expect(result.performUndo()).resolves.toEqual({
      kind: 'failed',
      error: failure,
    })

    expect(result.receipt.value).toEqual(receipt)
    expect(setStatus).not.toHaveBeenCalled()
    expect(reportError).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('keeps a receipt and choice installed while performUndo is pending', async () => {
    const { choice, result } = setup()
    const newer: UndoReceipt = {
      item: 'beta.txt',
      entry: '{"ts": "later", "item": "beta.txt"}',
      digest: 'b'.repeat(64),
    }
    const pending = deferred<UndoHistoryResponse>()
    choice.setPicked({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    })
    result.setReceipt(receipt)
    vi.spyOn(api, 'undoHistory').mockReturnValue(pending.promise)

    const first = result.performUndo()
    await flushPromises()
    result.setReceipt(newer)
    choice.setPicked({
      item: 'beta.txt',
      path: '/tmp/choosier/beta.txt',
      preview: null,
    })
    pending.resolve(undoResponse())

    await expect(first).resolves.toEqual({ kind: 'undone', item: 'alpha.txt' })
    expect(result.receipt.value).toEqual(newer)
    expect(choice.choice.value?.item).toBe('beta.txt')
  })
})
