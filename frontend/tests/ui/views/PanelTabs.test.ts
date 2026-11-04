import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { PanelTab, TabId } from '../../../src/view-models.ts'
import PanelTabs from '../../../src/views/PanelTabs.vue'

const TABS: readonly PanelTab[] = [
  { id: 'remaining', label: 'Remaining' },
  { id: 'history', label: 'History' },
  { id: 'browse', label: 'Browse' },
  { id: 'options', label: 'Options' },
]

const counts = (
  overrides: Partial<Record<TabId, number | null>> = {},
): Record<TabId, number | null> => ({
  remaining: null,
  history: null,
  browse: null,
  options: null,
  ...overrides,
})

function mountTabs(
  overrides: Partial<{
    tabs: readonly PanelTab[]
    activeTab: TabId
    counts: Record<TabId, number | null>
  }> = {},
) {
  return mount(PanelTabs, {
    props: {
      tabs: TABS,
      activeTab: 'remaining',
      counts: counts(),
      ...overrides,
    },
  })
}

describe('PanelTabs', () => {
  it('renders the tablist with one tab per panel', () => {
    const wrapper = mountTabs()

    const nav = wrapper.find('nav')
    expect(nav.classes()).toContain('tabs')
    expect(nav.attributes('role')).toBe('tablist')
    expect(nav.attributes('aria-label')).toBe('Folder panels')

    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(4)
    expect(buttons.map((button) => button.text())).toEqual([
      'Remaining',
      'History',
      'Browse',
      'Options',
    ])
    expect(buttons.map((button) => button.attributes('id'))).toEqual([
      'tab-remaining',
      'tab-history',
      'tab-browse',
      'tab-options',
    ])
    expect(buttons.every((button) => button.attributes('type') === 'button')).toBe(
      true,
    )
  })

  it('marks the active tab with selection, class, and a roving tabindex', () => {
    const wrapper = mountTabs({ activeTab: 'history' })
    const buttons = wrapper.findAll('button')

    expect(buttons.map((button) => button.attributes('role'))).toEqual([
      'tab',
      'tab',
      'tab',
      'tab',
    ])
    expect(buttons.map((button) => button.attributes('aria-selected'))).toEqual([
      'false',
      'true',
      'false',
      'false',
    ])
    expect(buttons.map((button) => button.attributes('tabindex'))).toEqual([
      '-1',
      '0',
      '-1',
      '-1',
    ])
    expect(buttons[1]?.classes()).toContain('active')
    expect(buttons[0]?.classes()).not.toContain('active')
  })

  it('points every tab at its panel', () => {
    const wrapper = mountTabs()

    expect(
      wrapper.findAll('button').map((button) => button.attributes('aria-controls')),
    ).toEqual([
      'panel-remaining',
      'panel-history',
      'panel-browse',
      'panel-options',
    ])
  })

  it('renders counts only when a value is present, including zero', () => {
    const wrapper = mountTabs({
      counts: counts({ remaining: 0, history: 12, browse: null, options: null }),
    })
    const buttons = wrapper.findAll('button')

    expect(buttons[0]?.find('.count').text()).toBe('0')
    expect(buttons[1]?.find('.count').text()).toBe('12')
    expect(buttons[2]?.find('.count').exists()).toBe(false)
    expect(buttons[3]?.find('.count').exists()).toBe(false)
  })

  it('emits select with the tab id on click', async () => {
    const wrapper = mountTabs()

    await wrapper.findAll('button')[3]?.trigger('click')

    expect(wrapper.emitted('select')).toEqual([['options']])
  })

  it('emits keydown with the original event and the tab id', async () => {
    const wrapper = mountTabs()

    await wrapper.findAll('button')[1]?.trigger('keydown', { key: 'ArrowRight' })

    const events = wrapper.emitted('keydown')
    expect(events).toHaveLength(1)
    expect(events?.[0]?.[0]).toBeInstanceOf(KeyboardEvent)
    expect((events?.[0]?.[0] as KeyboardEvent).key).toBe('ArrowRight')
    expect(events?.[0]?.[1]).toBe('history')
  })

  it('renders an empty tablist when no tabs are defined', () => {
    const wrapper = mountTabs({ tabs: [] })

    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.find('nav').attributes('role')).toBe('tablist')
  })
})
