import { nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useWorkspace } from '../../../src/state/use-workspace.ts'
import type {
  HistoryEntry,
  PreviewModel,
  RemoveHistoryItemsResponse,
  StateResponse,
} from '../../../src/types.ts'
import { deferred, flushPromises, mountHost } from '../test-helpers.ts'

const stateResponse = (
  overrides: Partial<StateResponse> = {},
): StateResponse => ({
  valid_path: true,
  path: '/tmp/choosier',
  log_file: '/tmp/choosier/.choosier.jsonl',
  remaining: ['alpha.txt'],
  remaining_total: 1,
  history: [],
  history_total: 0,
  ...overrides,
})

const historyEntry = (item: string, index: number): HistoryEntry => ({
  timestamp: `2026-11-04T09:${String(15 + index).padStart(2, '0')}:00+00:00`,
  item,
  display: item,
})

const textPreview = (text: string): PreviewModel => ({
  kind: 'text',
  text,
  truncated: false,
  entry_count: null,
  size: text.length,
  images: [],
  image_total: 0,
  video: null,
})

function setup(
  defaults = { path: '', log_file: '' },
  state = stateResponse(),
) {
  vi.spyOn(api, 'defaults').mockResolvedValue(defaults)
  vi.spyOn(api, 'state').mockResolvedValue(state)
  vi.spyOn(api, 'browse').mockResolvedValue({
    path: defaults.path,
    parent: '/tmp',
    entries: [],
  })
  const { result, wrapper } = mountHost(() => useWorkspace())
  return { workspace: result, wrapper }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('useWorkspace', () => {
  it('composes the baseline binding surface and loads defaults once', async () => {
    const { workspace, wrapper } = setup()

    await flushPromises()

    expect(api.defaults).toHaveBeenCalledTimes(1)
    expect(workspace.status.value).toBe('Choose a folder, then press Pick.')
    expect(workspace.tabs.map((tab) => tab.label)).toEqual([
      'Remaining',
      'History',
      'Browse',
      'Options',
    ])
    expect(workspace.activeTab.value).toBe('remaining')
    expect(workspace.path.value).toBe('')
    expect(workspace.logFile.value).toBe('')
    expect(workspace.seed.value).toBe('')
    expect(workspace.dryRun.value).toBe(false)
    expect(workspace.includeHidden.value).toBe(false)
    expect(workspace.mode.value).toBe('all')
    expect(workspace.state.value).toBeNull()
    expect(workspace.choice.value).toBeNull()
    expect(workspace.pickSerial.value).toBe(0)
    expect(workspace.clearing.value).toBe(false)
    expect(workspace.historyChecked.value).toEqual([])
    expect(workspace.pendingHistoryDelete.value).toBeNull()
    expect(workspace.historyDeleteCount.value).toBe(0)
    expect(workspace.historyDeleteMessage.value).toBe('')
    expect(workspace.historyDeleteLabel.value).toBe('Delete 0 items')
    expect(workspace.tabCounts.value.remaining).toBeNull()

    wrapper.unmount()
  })

  it('applies mounted defaults to the binding and refreshes state', async () => {
    const { workspace, wrapper } = setup({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/custom.jsonl',
    })

    await flushPromises()

    expect(workspace.path.value).toBe('/tmp/choosier')
    expect(workspace.logFile.value).toBe('/tmp/choosier/custom.jsonl')
    expect(workspace.state.value?.remaining_total).toBe(1)
    expect(workspace.tabCounts.value.remaining).toBe(1)

    wrapper.unmount()
  })

  it('path changes invalidate the choice and clear selection and pending delete', async () => {
    const { workspace, wrapper } = setup()
    await flushPromises()

    workspace.path.value = '/tmp/choosier'
    await nextTick()
    workspace.choice.value = {
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    }
    workspace.pickSerial.value = 4
    workspace.historyChecked.value = ['alpha.txt']
    workspace.requestDeleteSelected()
    expect(workspace.pendingHistoryDelete.value).toEqual(['alpha.txt'])

    workspace.path.value = '/tmp/choosier/next'
    await nextTick()

    expect(workspace.choice.value).toBeNull()
    expect(workspace.pickSerial.value).toBe(4)
    expect(workspace.historyChecked.value).toEqual([])
    expect(workspace.pendingHistoryDelete.value).toBeNull()

    wrapper.unmount()
  })

  it('log changes clear selection and pending delete but keep the choice', async () => {
    const { workspace, wrapper } = setup()
    await flushPromises()

    workspace.path.value = '/tmp/choosier'
    await nextTick()
    workspace.choice.value = {
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview: null,
    }
    workspace.historyChecked.value = ['alpha.txt']
    workspace.requestDeleteSelected()

    workspace.logFile.value = '/tmp/choosier/custom.jsonl'
    await nextTick()

    expect(workspace.choice.value?.item).toBe('alpha.txt')
    expect(workspace.historyChecked.value).toEqual([])
    expect(workspace.pendingHistoryDelete.value).toBeNull()

    wrapper.unmount()
  })

  it('exposes tab selection and keeps the tabs unit as the owner', async () => {
    const { workspace, wrapper } = setup()
    await flushPromises()

    workspace.onTabSelect('history')
    expect(workspace.activeTab.value).toBe('history')

    wrapper.unmount()
  })

  it('debounces rapid filter changes into one refresh with the composed filters', async () => {
    const { workspace, wrapper } = setup()
    await flushPromises()

    vi.useFakeTimers()

    workspace.path.value = '/tmp/choosier'
    await nextTick()
    await vi.advanceTimersByTimeAsync(250)

    const state = vi.mocked(api.state)
    state.mockClear()

    workspace.includeHidden.value = true
    await nextTick()
    workspace.mode.value = 'files'
    await nextTick()
    workspace.mode.value = 'dirs'
    await nextTick()

    await vi.advanceTimersByTimeAsync(249)
    expect(state).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(state).toHaveBeenCalledTimes(1)
    expect(state).toHaveBeenCalledWith({
      path: '/tmp/choosier',
      log_file: '',
      include_hidden: true,
      files_only: false,
      dirs_only: true,
    })

    wrapper.unmount()
  })

  it('keeps only the newest history preview when responses resolve out of order', async () => {
    const alpha = deferred<PreviewModel>()
    const beta = deferred<PreviewModel>()
    vi.spyOn(api, 'preview')
      .mockReturnValueOnce(alpha.promise)
      .mockReturnValueOnce(beta.promise)

    const { workspace, wrapper } = setup(
      { path: '/tmp/choosier', log_file: '/tmp/choosier/.choosier.jsonl' },
      stateResponse({
        history: [historyEntry('alpha.txt', 0), historyEntry('beta.txt', 1)],
        history_total: 2,
      }),
    )
    await flushPromises()

    workspace.selectHistoryItem('alpha.txt', false)
    workspace.selectHistoryItem('beta.txt', false)

    alpha.resolve(textPreview('alpha body'))
    await flushPromises()

    expect(workspace.choice.value?.item).toBe('beta.txt')
    expect(workspace.choice.value?.preview).toBeNull()
    expect(workspace.status.value).toBe('Choose a folder, then press Pick.')

    beta.resolve(textPreview('beta body'))
    await flushPromises()

    expect(workspace.choice.value?.item).toBe('beta.txt')
    expect(workspace.choice.value?.preview?.text).toBe('beta body')
    expect(workspace.status.value).toBe('Previewing beta.txt from history.')

    wrapper.unmount()
  })

  it('binds browser navigation and Use this folder into the shared path', async () => {
    const { workspace, wrapper } = setup({
      path: '/tmp/choosier',
      log_file: '',
    })
    await flushPromises()

    const browse = vi.mocked(api.browse)
    browse.mockReset()
    browse.mockImplementation(async (path) => ({
      path,
      parent: '/tmp',
      entries: path.endsWith('/folder-a')
        ? [{ name: 'inner.txt', is_dir: false }]
        : [],
    }))

    expect(workspace.browserListing.value?.path).toBe('/tmp/choosier')

    workspace.navigateBrowser('/tmp/choosier/folder-a')
    await flushPromises()

    expect(browse).toHaveBeenLastCalledWith('/tmp/choosier/folder-a')
    expect(workspace.browserListing.value?.path).toBe(
      '/tmp/choosier/folder-a',
    )
    expect(workspace.browserListing.value?.entries).toEqual([
      { name: 'inner.txt', is_dir: false },
    ])

    workspace.useBrowserFolder()
    await nextTick()
    expect(workspace.path.value).toBe('/tmp/choosier/folder-a')

    wrapper.unmount()
  })

  it('runs the clear confirmation lifecycle without clearing on cancel', async () => {
    const clear = vi.spyOn(api, 'clear').mockResolvedValue({
      log_file: '/tmp/choosier/.choosier.jsonl',
      removed: true,
    })
    const { workspace, wrapper } = setup({
      path: '/tmp/choosier',
      log_file: '/tmp/choosier/.choosier.jsonl',
    })
    await flushPromises()

    workspace.requestClear()
    expect(workspace.clearing.value).toBe(true)
    expect(workspace.clearMessage.value).toBe(
      'Clear history?\n/tmp/choosier/.choosier.jsonl',
    )

    workspace.cancelClear()
    expect(workspace.clearing.value).toBe(false)
    expect(clear).not.toHaveBeenCalled()

    workspace.requestClear()
    const refreshes = vi.mocked(api.state).mock.calls.length
    await workspace.confirmClear()

    expect(clear).toHaveBeenCalledWith(
      '/tmp/choosier',
      '/tmp/choosier/.choosier.jsonl',
    )
    expect(workspace.clearing.value).toBe(false)
    expect(workspace.status.value).toBe(
      'Cleared /tmp/choosier/.choosier.jsonl.',
    )
    expect(vi.mocked(api.state).mock.calls.length).toBeGreaterThan(refreshes)

    wrapper.unmount()
  })

  it('runs the batch delete confirmation lifecycle and busy flag', async () => {
    const removal = deferred<RemoveHistoryItemsResponse>()
    vi.spyOn(api, 'removeHistoryItems').mockReturnValue(removal.promise)

    const { workspace, wrapper } = setup(
      { path: '/tmp/choosier', log_file: '/tmp/choosier/.choosier.jsonl' },
      stateResponse({
        history: [
          historyEntry('alpha.txt', 0),
          historyEntry('beta.txt', 1),
          historyEntry('gamma.txt', 2),
        ],
        history_total: 3,
      }),
    )
    await flushPromises()

    workspace.historyChecked.value = ['alpha.txt', 'beta.txt']
    workspace.requestDeleteSelected()
    expect(workspace.pendingHistoryDelete.value).toEqual([
      'alpha.txt',
      'beta.txt',
    ])
    expect(workspace.historyDeleteLabel.value).toBe('Delete 2 items')

    workspace.cancelDeleteSelected()
    expect(workspace.pendingHistoryDelete.value).toBeNull()

    workspace.requestDeleteSelected()
    const confirmation = workspace.confirmDeleteSelected()
    await nextTick()

    expect(workspace.pendingHistoryDelete.value).toBeNull()
    expect(workspace.removingHistory.value).toBe(true)

    removal.resolve({
      log_file: '/tmp/choosier/.choosier.jsonl',
      items: ['alpha.txt', 'beta.txt'],
      removed: 2,
    })
    await confirmation

    expect(workspace.removingHistory.value).toBe(false)
    expect(workspace.status.value).toBe('Removed 2 entries from history.')
    expect(workspace.historyChecked.value).toEqual([])

    wrapper.unmount()
  })
})
