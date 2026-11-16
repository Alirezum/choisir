import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmptyState from '../../../src/components/EmptyState.vue'
import PanelShell from '../../../src/components/PanelShell.vue'
import RemainingPanel from '../../../src/views/RemainingPanel.vue'

describe('RemainingPanel', () => {
  it('renders through the shared shell with the live count and every row', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt', 'beta.txt'], total: 2 },
    })

    expect(wrapper.findComponent(PanelShell).exists()).toBe(true)
    expect(wrapper.find('.panel-header').text()).toBe('2 remaining')
    const rows = wrapper.findAll('.name-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.text()).toContain('alpha.txt')
    expect(rows[1]?.attributes('title')).toBe('beta.txt')
  })

  it('shows the truncated first-N header copy', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt'], total: 5 },
    })

    expect(wrapper.find('.panel-header').text()).toBe(
      '5 remaining (showing the first 1)',
    )
  })

  it('shows the all-picked empty copy through the shared empty state', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: [], total: 0 },
    })

    expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
    expect(wrapper.find('.panel-empty').text()).toBe(
      'Everything in this folder has been picked.',
    )
  })

  it('shows the filtered-empty copy when options hide the remaining rows', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: [], total: 3 },
    })

    expect(wrapper.find('.panel-empty').text()).toBe(
      'No items match the current options.',
    )
  })

  it('renders one Not now button per remaining row', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt', 'beta.txt'], total: 2 },
    })

    const buttons = wrapper.findAll('button.skip-button')
    expect(buttons).toHaveLength(2)
    expect(buttons.map((button) => button.text())).toEqual(['Not now', 'Not now'])
    expect(buttons[0]?.attributes('aria-label')).toBe('Skip alpha.txt')
    expect(buttons[1]?.attributes('aria-label')).toBe('Skip beta.txt')
    expect(buttons[0]?.attributes('type')).toBe('button')
  })

  it('emits the row name when its button is clicked', async () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt', 'beta.txt'], total: 2 },
    })

    await wrapper.findAll('button.skip-button')[1]?.trigger('click')

    expect(wrapper.emitted('skip')).toEqual([['beta.txt']])
  })

  it('emits the row name from the keyboard on the focused button', async () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt'], total: 1 },
    })
    const button = wrapper.find('button.skip-button')
    button.element.focus()

    await button.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('skip')).toEqual([['alpha.txt']])
  })

  it('renders no buttons when the list is empty', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: [], total: 0 },
    })

    expect(wrapper.find('button').exists()).toBe(false)
  })
})
