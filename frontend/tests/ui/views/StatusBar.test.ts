import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatusBar from '../../../src/views/StatusBar.vue'

describe('StatusBar', () => {
  it('renders the message inside a polite status live region', () => {
    const wrapper = mount(StatusBar, { props: { message: 'Picked only.txt.' } })

    const footer = wrapper.element
    expect(footer.className).toBe('status')
    expect(footer.getAttribute('role')).toBe('status')
    expect(footer.getAttribute('aria-live')).toBe('polite')
    expect(wrapper.text()).toBe('Picked only.txt.')
  })

  it('replaces the whole message when the prop changes', async () => {
    const wrapper = mount(StatusBar, {
      props: { message: 'Choose a folder, then press Pick.' },
    })

    await wrapper.setProps({ message: 'Opened only.txt.' })

    expect(wrapper.text()).toBe('Opened only.txt.')
  })
})
