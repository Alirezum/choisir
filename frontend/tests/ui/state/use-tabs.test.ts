import { nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { PANEL_TABS, useTabs } from '../../../src/state/use-tabs.ts'
import type { StateResponse } from '../../../src/types.ts'

const stateResponse = (
  remainingTotal: number,
  historyTotal: number,
): StateResponse => ({
  valid_path: true,
  path: '/tmp/choosier',
  log_file: '',
  remaining: [],
  remaining_total: remainingTotal,
  history: [],
  history_total: historyTotal,
})

function setup() {
  document.body.innerHTML = PANEL_TABS.map(
    (tab) => `<button id="tab-${tab.id}">${tab.label}</button>`,
  ).join('')
  const state = ref<StateResponse | null>(null)
  const tabs = useTabs({ state })
  return { state, tabs }
}

describe('useTabs', () => {
  it('exposes the baseline tab strip and starts on Remaining', () => {
    const { tabs } = setup()

    expect(tabs.tabs.map((tab) => tab.label)).toEqual([
      'Remaining',
      'History',
      'Browse',
      'Options',
    ])
    expect(tabs.activeTab.value).toBe('remaining')
    expect(tabs.count('remaining')).toBeNull()
    expect(tabs.count('history')).toBeNull()
    expect(tabs.count('browse')).toBeNull()
    expect(tabs.count('options')).toBeNull()
  })

  it('returns the state counts for Remaining and History only', () => {
    const { state, tabs } = setup()

    state.value = stateResponse(7, 3)

    expect(tabs.count('remaining')).toBe(7)
    expect(tabs.count('history')).toBe(3)
    expect(tabs.count('browse')).toBeNull()
    expect(tabs.count('options')).toBeNull()
  })

  it('selects a tab', () => {
    const { tabs } = setup()

    tabs.select('history')

    expect(tabs.activeTab.value).toBe('history')
  })

  it('moves right and wraps at the end', async () => {
    const { tabs } = setup()

    tabs.activeTab.value = 'remaining'
    tabs.onKey(new KeyboardEvent('keydown', { key: 'ArrowRight' }), 'remaining')
    await nextTick()
    expect(tabs.activeTab.value).toBe('history')
    expect(document.activeElement?.id).toBe('tab-history')

    tabs.onKey(new KeyboardEvent('keydown', { key: 'ArrowRight' }), 'options')
    await nextTick()
    expect(tabs.activeTab.value).toBe('remaining')
    expect(document.activeElement?.id).toBe('tab-remaining')
  })

  it('moves left and wraps at the start', async () => {
    const { tabs } = setup()

    tabs.activeTab.value = 'remaining'
    tabs.onKey(new KeyboardEvent('keydown', { key: 'ArrowLeft' }), 'remaining')
    await nextTick()
    expect(tabs.activeTab.value).toBe('options')
    expect(document.activeElement?.id).toBe('tab-options')
  })

  it('jumps Home and End, moving focus with the active tab', async () => {
    const { tabs } = setup()

    tabs.activeTab.value = 'browse'
    tabs.onKey(new KeyboardEvent('keydown', { key: 'Home' }), 'browse')
    await nextTick()
    expect(tabs.activeTab.value).toBe('remaining')
    expect(document.activeElement?.id).toBe('tab-remaining')

    tabs.onKey(new KeyboardEvent('keydown', { key: 'End' }), 'remaining')
    await nextTick()
    expect(tabs.activeTab.value).toBe('options')
    expect(document.activeElement?.id).toBe('tab-options')
  })

  it('ignores other keys without preventing their default', () => {
    const { tabs } = setup()
    const event = new KeyboardEvent('keydown', { key: 'a', cancelable: true })
    const preventDefault = vi.spyOn(event, 'preventDefault')

    tabs.onKey(event, 'remaining')

    expect(tabs.activeTab.value).toBe('remaining')
    expect(preventDefault).not.toHaveBeenCalled()
  })

  it('prevents default and updates the active tab for handled keys', async () => {
    const { tabs } = setup()
    const event = new KeyboardEvent('keydown', {
      key: 'ArrowRight',
      cancelable: true,
    })
    const preventDefault = vi.spyOn(event, 'preventDefault')

    tabs.onKey(event, 'remaining')

    expect(preventDefault).toHaveBeenCalledTimes(1)
    expect(tabs.activeTab.value).toBe('history')
    await nextTick()
  })
})
