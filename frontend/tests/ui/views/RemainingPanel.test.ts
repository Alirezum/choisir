import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmptyState from '../../../src/components/EmptyState.vue'
import PanelShell from '../../../src/components/PanelShell.vue'
import type { SkippedRow } from '../../../src/state/use-skip.ts'
import RemainingPanel from '../../../src/views/RemainingPanel.vue'

interface PanelProps {
  items: string[]
  total: number
  skipped: SkippedRow[]
  skippedTotal: number
  allSkipped: boolean
}

function mountPanel(overrides: Partial<PanelProps> = {}) {
  return mount(RemainingPanel, {
    props: {
      items: ['alpha.txt'],
      total: 1,
      skipped: [],
      skippedTotal: 0,
      allSkipped: false,
      ...overrides,
    },
  })
}

describe('RemainingPanel', () => {
  it('renders through the shared shell with the live count and every row', () => {
    const wrapper = mountPanel({
      items: ['alpha.txt', 'beta.txt'],
      total: 2,
    })

    expect(wrapper.findComponent(PanelShell).exists()).toBe(true)
    expect(wrapper.find('.panel-header').text()).toBe('2 remaining')
    const rows = wrapper.findAll('.name-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.text()).toContain('alpha.txt')
    expect(rows[1]?.attributes('title')).toBe('beta.txt')
  })

  it('shows the truncated first-N header copy', () => {
    const wrapper = mountPanel({ items: ['alpha.txt'], total: 5 })

    expect(wrapper.find('.panel-header').text()).toBe(
      '5 remaining (showing the first 1)',
    )
  })

  it('shows the all-picked empty copy through the shared empty state', () => {
    const wrapper = mountPanel({ items: [], total: 0 })

    expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
    expect(wrapper.find('.panel-empty').text()).toBe(
      'Everything in this folder has been picked.',
    )
  })

  it('shows the filtered-empty copy when options hide the remaining rows', () => {
    const wrapper = mountPanel({ items: [], total: 3 })

    expect(wrapper.find('.panel-empty').text()).toBe(
      'No items match the current options.',
    )
  })

  it('renders one Not now button per remaining row', () => {
    const wrapper = mountPanel({
      items: ['alpha.txt', 'beta.txt'],
      total: 2,
    })

    const buttons = wrapper.findAll('button.skip-button')
    expect(buttons).toHaveLength(2)
    expect(buttons.map((button) => button.text())).toEqual(['Not now', 'Not now'])
    expect(buttons[0]?.attributes('aria-label')).toBe('Skip alpha.txt')
    expect(buttons[1]?.attributes('aria-label')).toBe('Skip beta.txt')
    expect(buttons[0]?.attributes('type')).toBe('button')
  })

  it('emits the row name when its button is clicked', async () => {
    const wrapper = mountPanel({
      items: ['alpha.txt', 'beta.txt'],
      total: 2,
    })

    await wrapper.findAll('button.skip-button')[1]?.trigger('click')

    expect(wrapper.emitted('skip')).toEqual([['beta.txt']])
  })

  it('emits the row name from the keyboard on the focused button', async () => {
    const wrapper = mountPanel()
    const button = wrapper.find('button.skip-button')
    button.element.focus()

    await button.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('skip')).toEqual([['alpha.txt']])
  })

  it('renders the skipped rows with their countdowns', () => {
    const wrapper = mountPanel({
      items: ['alpha.txt'],
      total: 1,
      skipped: [
        { name: 'beta.txt', returnsIn: '9:59' },
        { name: 'gamma', returnsIn: '10:00' },
      ],
      skippedTotal: 2,
    })

    const rows = wrapper.findAll('.skipped-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.find('.skipped-text').text()).toBe(
      'beta.txt — returns in 9:59',
    )
    expect(rows[1]?.find('.skipped-text').text()).toBe(
      'gamma — returns in 10:00',
    )
    expect(wrapper.find('.skipped-heading').text()).toBe('Skipped')
  })

  it('emits a restore with the row name and accessible return time', async () => {
    const wrapper = mountPanel({
      skipped: [{ name: 'beta.txt', returnsIn: '9:59' }],
      skippedTotal: 1,
    })
    const button = wrapper.find('button.restore-button')

    expect(button.attributes('aria-label')).toBe(
      'Restore beta.txt, returns in 9:59',
    )
    await button.trigger('click')

    expect(wrapper.emitted('restore')).toEqual([['beta.txt']])
  })

  it('emits restore-all when skipped rows are displayed', async () => {
    const wrapper = mountPanel({
      skipped: [{ name: 'beta.txt', returnsIn: '9:59' }],
      skippedTotal: 1,
    })
    const button = wrapper.find('button.restore-all')

    expect(button.attributes('disabled')).toBeUndefined()
    await button.trigger('click')

    expect(wrapper.emitted('restore-all')).toEqual([[]])
  })

  it('disables restore-all when nothing is skipped', () => {
    const wrapper = mountPanel()

    expect(wrapper.find('button.restore-all').attributes('disabled')).toBeDefined()
  })

  it('distinguishes the all-skipped empty state', () => {
    const wrapper = mountPanel({
      items: [],
      total: 0,
      skipped: [{ name: 'alpha.txt', returnsIn: '9:59' }],
      skippedTotal: 1,
      allSkipped: true,
    })

    expect(wrapper.find('.panel-empty').text()).toBe(
      'Every available item is skipped. Restore skipped items to pick again.',
    )
    expect(wrapper.find('button.restore-all').attributes('disabled')).toBeUndefined()
  })

  it('uses the neutral message when nothing remains but skips are displayed', () => {
    const wrapper = mountPanel({
      items: [],
      total: 0,
      skipped: [{ name: 'alpha.txt', returnsIn: '9:59' }],
      skippedTotal: 1,
    })

    expect(wrapper.find('.panel-empty').text()).toBe(
      'No items are available right now.',
    )
    expect(wrapper.findAll('.skipped-row')).toHaveLength(1)
  })

  it('gives every control an accessible name in DOM order', () => {
    const wrapper = mountPanel({
      items: ['alpha.txt'],
      total: 1,
      skipped: [{ name: 'beta.txt', returnsIn: '9:59' }],
      skippedTotal: 1,
    })

    const names = wrapper.findAll('button').map((button) => {
      return button.attributes('aria-label') ?? button.text()
    })
    expect(names).toEqual([
      'Skip alpha.txt',
      'Restore beta.txt, returns in 9:59',
      'Restore all skipped items',
    ])
  })

  it('renders no skip buttons when the remaining list is empty', () => {
    const wrapper = mountPanel({ items: [], total: 0 })

    expect(wrapper.findAll('button.skip-button')).toHaveLength(0)
    expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
  })
})
