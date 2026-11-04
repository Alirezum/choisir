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
    expect(rows[0]?.text()).toBe('alpha.txt')
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

  it('renders rows as a plain list without interactive controls', () => {
    const wrapper = mount(RemainingPanel, {
      props: { items: ['alpha.txt'], total: 1 },
    })

    expect(wrapper.find('.list').classes()).toContain('list')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
