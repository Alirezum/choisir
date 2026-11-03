import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { describe, expect, it } from 'vitest'

import EmptyState from '../../../src/components/EmptyState.vue'

describe('EmptyState', () => {
  it('renders the shared panel-empty paragraph with slotted text', () => {
    const wrapper = mount(EmptyState, {
      slots: { default: 'Nothing here yet.' },
    })

    expect(wrapper.element.tagName).toBe('P')
    expect(wrapper.classes()).toContain('panel-empty')
    expect(wrapper.text()).toBe('Nothing here yet.')
  })

  it('merges an optional consumer class with the shared class', () => {
    const wrapper = mount(EmptyState, {
      attrs: { class: 'error' },
      slots: { default: 'Unreadable folder.' },
    })

    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['panel-empty', 'error']),
    )
  })

  it('keeps slotted markup and preserves text exactly', () => {
    const wrapper = mount(EmptyState, {
      slots: {
        default: () =>
          h('span', [
            'Browser playback failed. Use ',
            h('strong', 'Open'),
            ' above to play this file.',
          ]),
      },
    })

    expect(wrapper.find('strong').text()).toBe('Open')
    expect(wrapper.text()).toContain('Browser playback failed.')
  })
})
