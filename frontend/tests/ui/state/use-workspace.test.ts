import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useWorkspace } from '../../../src/state/use-workspace.ts'
import type { StateResponse } from '../../../src/types.ts'
import { flushPromises, mountHost } from '../test-helpers.ts'

const stateResponse = (): StateResponse => ({
  valid_path: true,
  path: '/tmp/choosier',
  log_file: '',
  remaining: ['alpha.txt'],
  remaining_total: 1,
  history: [],
  history_total: 0,
})

function setup(defaults = { path: '', log_file: '' }) {
  vi.spyOn(api, 'defaults').mockResolvedValue(defaults)
  vi.spyOn(api, 'state').mockResolvedValue(stateResponse())
  const { result, wrapper } = mountHost(() => useWorkspace())
  return { workspace: result, wrapper }
}

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
})
