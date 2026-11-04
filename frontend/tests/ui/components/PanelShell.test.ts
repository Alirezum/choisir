import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { describe, expect, it } from 'vitest'

import PanelShell from '../../../src/components/PanelShell.vue'

describe('PanelShell', () => {
  it('renders the shared panel scaffold, slots, header class, and title', () => {
    const wrapper = mount(PanelShell, {
      props: { headerClass: 'history-header', headerTitle: '/tmp/choosier' },
      attrs: { class: 'browser' },
      slots: {
        header: () => h('span', '5 picked'),
        default: () => h('p', { class: 'body-copy' }, 'Panel body'),
        actions: () => h('button', 'Archive history'),
      },
    })

    expect(wrapper.classes()).toEqual(expect.arrayContaining(['panel', 'browser']))
    expect(wrapper.find('.panel-header').classes()).toContain('history-header')
    expect(wrapper.find('.panel-header').attributes('title')).toBe(
      '/tmp/choosier',
    )
    expect(wrapper.find('.panel-header').text()).toBe('5 picked')
    expect(wrapper.find('.body-copy').text()).toBe('Panel body')
    expect(wrapper.find('.panel-actions').text()).toBe('Archive history')
  })

  it('omits the action wrapper when no actions slot is provided', () => {
    const wrapper = mount(PanelShell, {
      slots: {
        header: () => h('span', 'Header'),
        default: () => h('p', 'Body'),
      },
    })

    expect(wrapper.find('.panel-actions').exists()).toBe(false)
  })

  it('keeps the header, body, and actions in DOM order', () => {
    const wrapper = mount(PanelShell, {
      slots: {
        header: () => h('span', 'Header'),
        default: () => h('p', 'Body'),
        actions: () => h('button', 'Action'),
      },
    })

    const children = Array.from(wrapper.element.children).map((child) =>
      child.classList.contains('panel-header')
        ? 'header'
        : child.classList.contains('panel-actions')
          ? 'actions'
          : 'body',
    )
    expect(children).toEqual(['header', 'body', 'actions'])
  })

  it('keeps the shared class when the consumer supplies no extra class', () => {
    const wrapper = mount(PanelShell)

    expect(wrapper.classes()).toEqual(['panel'])
  })
})
