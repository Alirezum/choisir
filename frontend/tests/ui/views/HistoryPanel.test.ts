import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmptyState from '../../../src/components/EmptyState.vue'
import PanelShell from '../../../src/components/PanelShell.vue'
import HistoryPanel from '../../../src/views/HistoryPanel.vue'
import type { HistoryEntry } from '../../../src/types.ts'

const entry = (item: string, timestamp: string | null = null): HistoryEntry => ({
  timestamp,
  item,
  display: item,
})

function mountPanel(
  overrides: Partial<{
    entries: HistoryEntry[]
    total: number
    busy: boolean
    selected: string | null
    checkedItems: string[]
    header: string
    allSelected: boolean
    checkedCount: number
  }> = {},
) {
  return mount(HistoryPanel, {
    props: {
      entries: [entry('alpha.txt'), entry('beta.txt')],
      total: 2,
      busy: false,
      selected: null,
      checkedItems: [],
      header: '2 picked',
      allSelected: false,
      checkedCount: 0,
      ...overrides,
    },
  })
}

describe('HistoryPanel', () => {
  it('renders through the shared shell with the derived header and hint', () => {
    const wrapper = mountPanel()

    expect(wrapper.findComponent(PanelShell).exists()).toBe(true)
    expect(wrapper.find('.history-header span').text()).toBe('2 picked')
    expect(wrapper.find('.history-hint').text()).toBe(
      'Click a row to preview and select it. Shift-click to select a range.',
    )
  })

  it('renders every row with select, open, and remove controls', () => {
    const wrapper = mountPanel()

    const rows = wrapper.findAll('.history-row')
    expect(rows).toHaveLength(2)
    expect(wrapper.findAll('.history-select')).toHaveLength(2)
    expect(wrapper.findAll('.history-open')).toHaveLength(2)
    expect(wrapper.findAll('.history-delete')).toHaveLength(2)
    expect(wrapper.find('.history-text').text()).toBe('alpha.txt')
  })

  it('marks the selected and checked rows with aria state', () => {
    const wrapper = mountPanel({
      selected: 'beta.txt',
      checkedItems: ['alpha.txt'],
    })

    const [first, second] = wrapper.findAll('.history-row')
    expect(first?.classes()).toContain('is-checked')
    expect(second?.classes()).toContain('is-selected')
    expect(wrapper.findAll('.history-select')[0]?.attributes('aria-pressed')).toBe(
      'true',
    )
    expect(wrapper.findAll('.history-select')[1]?.attributes('aria-pressed')).toBe(
      'false',
    )
    expect(wrapper.findAll('.history-select')[1]?.attributes('aria-current')).toBe(
      'true',
    )
  })

  it('omits the time span content but keeps the semantic slot', () => {
    const wrapper = mountPanel()

    expect(wrapper.find('.history-time').text()).toBe('')
    expect(wrapper.find('.history-time').classes()).toContain('history-time')
  })

  it('keeps the timestamp in the datetime attribute when present', () => {
    const wrapper = mountPanel({
      entries: [entry('alpha.txt', '2026-11-03T14:04:30Z')],
    })

    expect(wrapper.find('.history-time').attributes('datetime')).toBe(
      '2026-11-03T14:04:30Z',
    )
    expect(wrapper.find('.history-time').text()).not.toBe('')
  })

  it('emits a plain select and a shift select with the shift flag', async () => {
    const wrapper = mountPanel()
    const select = wrapper.findAll('.history-select')[0]

    await select?.trigger('click')
    await select?.trigger('click', { shiftKey: true })

    expect(wrapper.emitted('select')).toEqual([
      ['alpha.txt', false],
      ['alpha.txt', true],
    ])
  })

  it('emits open, remove, archive, clear, toggleAll, and removeSelected intents', async () => {
    const wrapper = mountPanel({ checkedCount: 1 })

    await wrapper.find('.history-open').trigger('click')
    await wrapper.find('.history-delete').trigger('click')
    await wrapper.findAll('.panel-actions button')[1]?.trigger('click')
    await wrapper.findAll('.panel-actions button')[2]?.trigger('click')
    await wrapper.find('.panel-link').trigger('click')
    await wrapper.find('.panel-actions .danger').trigger('click')

    expect(wrapper.emitted('open')).toEqual([['alpha.txt']])
    expect(wrapper.emitted('remove')).toEqual([['alpha.txt']])
    expect(wrapper.emitted('archive')).toEqual([[]])
    expect(wrapper.emitted('clear')).toEqual([[]])
    expect(wrapper.emitted('toggleAll')).toEqual([[]])
    expect(wrapper.emitted('removeSelected')).toEqual([[]])
  })

  it('labels the select-all link from the allSelected prop and hides it without rows', () => {
    const withRows = mountPanel({ allSelected: true })
    expect(withRows.find('.panel-link').text()).toBe('Clear selection')

    const empty = mountPanel({ entries: [], total: 0, header: '0 picked' })
    expect(empty.find('.panel-link').exists()).toBe(false)
  })

  it('shows the delete-selected control only when items are checked', () => {
    const withChecks = mountPanel({ checkedCount: 3 })
    expect(withChecks.find('.panel-actions .danger').text()).toBe(
      'Delete selected (3)',
    )

    const withoutChecks = mountPanel()
    const actions = withoutChecks.findAll('.panel-actions button')
    expect(actions.map((button) => button.text())).toEqual([
      'Archive history',
      'Clear history',
    ])
  })

  it('disables the action controls while busy', () => {
    const wrapper = mountPanel({ busy: true, checkedCount: 1 })

    expect(wrapper.find('.history-open').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.history-delete').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.panel-link').attributes('disabled')).toBeDefined()
    for (const button of wrapper.findAll('.panel-actions button')) {
      expect(button.attributes('disabled')).toBeDefined()
    }
  })

  it('shows the empty copy through the shared empty state', () => {
    const wrapper = mountPanel({
      entries: [],
      total: 0,
      header: '0 picked',
    })

    expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
    expect(wrapper.find('.panel-empty').text()).toBe(
      'Picked items land here. Remove one to make it available again.',
    )
    expect(wrapper.find('.history-hint').exists()).toBe(false)
  })
})
