import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useChoice } from '../../../src/state/use-choice.ts'
import { useFolderOptions } from '../../../src/state/use-folder-options.ts'
import { useHistoryActions } from '../../../src/state/use-history-actions.ts'
import { useHistorySelection } from '../../../src/state/use-history-selection.ts'
import type { HistoryEntry, PreviewModel, StateResponse } from '../../../src/types.ts'
import { deferred } from '../test-helpers.ts'

const preview: PreviewModel = {
  kind: 'text',
  text: 'alpha',
  truncated: false,
  entry_count: null,
  size: 5,
  images: [],
  image_total: 0,
  video: null,
}

const entry = (item: string): HistoryEntry => ({
  timestamp: null,
  item,
  display: item,
})

function setup(items: string[] = ['alpha.txt', 'beta.txt', 'gamma.txt']) {
  const options = useFolderOptions()
  options.path.value = '/tmp/choosier'
  options.logFile.value = '/tmp/choosier/.choosier.jsonl'
  const choice = useChoice()
  const entries = ref<HistoryEntry[]>(items.map(entry))
  const selection = useHistorySelection({ entries: () => entries.value })
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const refresh = vi.fn(async () => {})
  const openEntry = vi.fn(async () => {})
  const state = ref<StateResponse | null>({
    valid_path: true,
    path: '/tmp/choosier',
    log_file: '',
    remaining: [],
    remaining_total: 0,
    history: entries.value,
    history_total: items.length,
  })

  const result = useHistoryActions({
    options,
    choice,
    selection,
    state,
    status: { setStatus, reportError },
    refresh,
    openEntry,
  })

  return {
    options,
    choice,
    entries,
    state,
    selection,
    setStatus,
    reportError,
    refresh,
    openEntry,
    result,
  }
}

describe('useHistoryActions', () => {
  it('archives history, reports the backup, refreshes, and clears selection', async () => {
    const { result, selection, setStatus, refresh } = setup()
    selection.addRange(['alpha.txt'])
    vi.spyOn(api, 'archive').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      backup: '/tmp/choosier/.choosier.jsonl.old',
    })

    await result.archive()

    expect(api.archive).toHaveBeenCalledWith(
      '/tmp/choosier',
      '/tmp/choosier/.choosier.jsonl',
    )
    expect(setStatus).toHaveBeenCalledWith(
      'Archived history to /tmp/choosier/.choosier.jsonl.old.',
    )
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(selection.checkedItems.value).toEqual([])
  })

  it('reports a missing history file and still refreshes', async () => {
    const { result, setStatus, refresh } = setup()
    vi.spyOn(api, 'archive').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      backup: null,
    })

    await result.archive()

    expect(setStatus).toHaveBeenCalledWith(
      'No history file at /tmp/choosier/.choosier.jsonl.',
    )
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('reports archive failures through the shared status path', async () => {
    const { result, reportError, refresh } = setup()
    const failure = new Error('archive failed')
    vi.spyOn(api, 'archive').mockRejectedValue(failure)

    await result.archive()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('opens and cancels the clear confirmation without a request', async () => {
    const { result } = setup()
    const clear = vi.spyOn(api, 'clear')

    result.requestClear()
    expect(result.clearing.value).toBe(true)

    result.cancelClear()
    expect(result.clearing.value).toBe(false)
    expect(clear).not.toHaveBeenCalled()
  })

  it('confirms clear immediately, reports the removed log, and refreshes', async () => {
    const { result, selection, setStatus, refresh } = setup()
    selection.addRange(['alpha.txt'])
    vi.spyOn(api, 'clear').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      removed: true,
    })
    result.requestClear()

    await result.confirmClear()

    expect(result.clearing.value).toBe(false)
    expect(setStatus).toHaveBeenCalledWith(
      'Cleared /tmp/choosier/.choosier.jsonl.',
    )
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(selection.checkedItems.value).toEqual([])
  })

  it('reports a missing log on clear and reports failures', async () => {
    const { result, setStatus, reportError, refresh } = setup()
    vi.spyOn(api, 'clear').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      removed: false,
    })

    result.requestClear()
    await result.confirmClear()

    expect(setStatus).toHaveBeenCalledWith(
      'No history file at /tmp/choosier/.choosier.jsonl.',
    )

    const failure = new Error('clear failed')
    vi.spyOn(api, 'clear').mockRejectedValue(failure)
    result.requestClear()
    await result.confirmClear()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it.each([
    [0, 'No history entry for "alpha.txt".'],
    [1, 'Removed "alpha.txt" from history.'],
    [3, 'Removed 3 entries for "alpha.txt".'],
  ])('reports %i removed entries for one item', async (removed, message) => {
    const { result, selection, setStatus, refresh } = setup()
    selection.addRange(['alpha.txt', 'beta.txt'])
    vi.spyOn(api, 'removeHistoryItem').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      item: 'alpha.txt',
      removed,
    })

    await result.removeOne('alpha.txt')

    expect(api.removeHistoryItem).toHaveBeenCalledWith(
      '/tmp/choosier',
      '/tmp/choosier/.choosier.jsonl',
      'alpha.txt',
    )
    expect(setStatus).toHaveBeenCalledWith(message)
    expect(result.removingItem.value).toBeNull()
    expect(selection.checkedItems.value).toEqual(['beta.txt'])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('ignores a second single removal while one is in flight', async () => {
    const { result } = setup()
    const pending = deferred<{
      log_file: string
      item: string
      removed: number
    }>()
    vi.spyOn(api, 'removeHistoryItem').mockReturnValue(pending.promise)

    const first = result.removeOne('alpha.txt')
    await result.removeOne('beta.txt')

    expect(api.removeHistoryItem).toHaveBeenCalledTimes(1)
    pending.resolve({
      log_file: '/tmp/choosier/.choosier.jsonl',
      item: 'alpha.txt',
      removed: 1,
    })
    await first
  })

  it('reports a single removal failure and still cleans up', async () => {
    const { result, selection, reportError, refresh } = setup()
    const failure = new Error('remove failed')
    selection.addRange(['alpha.txt', 'beta.txt'])
    vi.spyOn(api, 'removeHistoryItem').mockRejectedValue(failure)

    await result.removeOne('alpha.txt')

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(result.removingItem.value).toBeNull()
    expect(selection.checkedItems.value).toEqual(['beta.txt'])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('copies the checked items into a pending batch and cancels cleanly', () => {
    const { result, selection } = setup()
    selection.addRange(['alpha.txt', 'beta.txt'])

    result.requestDeleteSelected()
    expect(result.pendingHistoryDelete.value).toEqual(['alpha.txt', 'beta.txt'])
    expect(result.historyDeleteCount.value).toBe(2)
    expect(result.historyDeleteMessage.value).toBe(
      'Delete history for 2 items?\nThis removes every log entry for the selected items, making them pickable again.',
    )
    expect(result.historyDeleteLabel.value).toBe('Delete 2 items')

    result.cancelDelete()
    expect(result.pendingHistoryDelete.value).toBeNull()
  })

  it('does not open a batch confirmation with no checked items', () => {
    const { result } = setup()

    result.requestDeleteSelected()

    expect(result.pendingHistoryDelete.value).toBeNull()
  })

  it('uses singular copy for one pending item', () => {
    const { result, selection } = setup()
    selection.addRange(['alpha.txt'])

    result.requestDeleteSelected()

    expect(result.historyDeleteMessage.value).toContain(
      'Delete history for 1 item?',
    )
    expect(result.historyDeleteLabel.value).toBe('Delete 1 item')
  })

  it.each([
    [0, 'No matching history entries to remove.'],
    [1, 'Removed 1 entry from history.'],
    [4, 'Removed 4 entries from history.'],
  ])('reports %i removed entries for a batch', async (removed, message) => {
    const { result, selection, setStatus, refresh } = setup()
    selection.addRange(['alpha.txt', 'beta.txt'])
    vi.spyOn(api, 'removeHistoryItems').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      items: ['alpha.txt', 'beta.txt'],
      removed,
    })
    result.requestDeleteSelected()

    await result.confirmDeleteSelected()

    expect(api.removeHistoryItems).toHaveBeenCalledWith(
      '/tmp/choosier',
      '/tmp/choosier/.choosier.jsonl',
      ['alpha.txt', 'beta.txt'],
    )
    expect(setStatus).toHaveBeenCalledWith(message)
    expect(result.pendingHistoryDelete.value).toBeNull()
    expect(result.removingHistory.value).toBe(false)
    expect(selection.checkedItems.value).toEqual([])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('does nothing when confirming without a pending batch', async () => {
    const { result } = setup()
    const remove = vi.spyOn(api, 'removeHistoryItems')

    await result.confirmDeleteSelected()

    expect(remove).not.toHaveBeenCalled()
  })

  it('reports a batch failure and still cleans up', async () => {
    const { result, selection, reportError, refresh } = setup()
    const failure = new Error('batch failed')
    selection.addRange(['alpha.txt'])
    vi.spyOn(api, 'removeHistoryItems').mockRejectedValue(failure)
    result.requestDeleteSelected()

    await result.confirmDeleteSelected()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(result.removingHistory.value).toBe(false)
    expect(selection.checkedItems.value).toEqual([])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('previews a history item and reports it only when the response is current', async () => {
    const { result, choice, setStatus } = setup()
    vi.spyOn(api, 'preview').mockResolvedValue(preview)

    await result.previewHistoryItem('alpha.txt')

    expect(api.preview).toHaveBeenCalledWith('/tmp/choosier/alpha.txt')
    expect(choice.choice.value).toEqual({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview,
    })
    expect(setStatus).toHaveBeenCalledWith(
      'Previewing alpha.txt from history.',
    )
  })

  it('ignores a preview response superseded by an invalidated choice', async () => {
    const { result, choice, setStatus, reportError } = setup()
    const pending = deferred<PreviewModel>()
    vi.spyOn(api, 'preview').mockReturnValue(pending.promise)

    const request = result.previewHistoryItem('alpha.txt')
    choice.invalidate()
    pending.resolve(preview)
    await request

    expect(choice.choice.value).toBeNull()
    expect(setStatus).not.toHaveBeenCalled()
    expect(reportError).not.toHaveBeenCalled()
  })

  it('ignores a stale preview failure but reports a current one', async () => {
    const { result, choice, reportError } = setup()
    const stale = deferred<PreviewModel>()
    vi.spyOn(api, 'preview').mockReturnValueOnce(stale.promise)

    const request = result.previewHistoryItem('alpha.txt')
    choice.invalidate()
    stale.reject(new Error('stale'))
    await request
    expect(reportError).not.toHaveBeenCalled()

    const failure = new Error('current')
    vi.spyOn(api, 'preview').mockRejectedValueOnce(failure)
    await result.previewHistoryItem('beta.txt')

    expect(reportError).toHaveBeenCalledWith(failure)
  })

  it('opens a history item through the entry path', () => {
    const { result, openEntry } = setup()

    result.openHistoryItem('alpha.txt')

    expect(openEntry).toHaveBeenCalledWith('/tmp/choosier/alpha.txt')
  })

  it('derives the history header from the loaded state', () => {
    const { result, state } = setup(['alpha.txt', 'beta.txt'])

    expect(result.historyHeader.value).toBe('2 picked')

    state.value = {
      valid_path: true,
      path: '/tmp/choosier',
      log_file: '',
      remaining: [],
      remaining_total: 0,
      history: entriesOf(['alpha.txt']),
      history_total: 5,
    }
    expect(result.historyHeader.value).toBe('5 picked (showing the last 1)')

    state.value = null
    expect(result.historyHeader.value).toBe('0 picked')
  })
})

function entriesOf(items: string[]): HistoryEntry[] {
  return items.map(entry)
}
