import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfirmDialog from '../../../src/views/ConfirmDialog.vue'

describe('ConfirmDialog', () => {
  it('splits the message into a title and detail inside an accessible dialog', () => {
    const wrapper = mount(ConfirmDialog, {
      props: { message: 'Clear history?\n/tmp/choosier/.choosier.jsonl' },
    })

    const overlay = wrapper.find('.overlay')
    expect(overlay.exists()).toBe(true)
    const dialog = wrapper.find('.dialog')
    expect(dialog.attributes('role')).toBe('dialog')
    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.attributes('aria-labelledby')).toBe('confirm-title')
    expect(wrapper.find('.dialog-title').text()).toBe('Clear history?')
    expect(wrapper.find('.dialog-detail').text()).toBe(
      '/tmp/choosier/.choosier.jsonl',
    )
  })

  it('renders default labels with the cancel button focused and first', () => {
    const wrapper = mount(ConfirmDialog, {
      props: { message: 'Clear history?' },
      attachTo: document.body,
    })

    const buttons = wrapper.findAll('.dialog-actions button')
    expect(buttons.map((button) => button.text())).toEqual([
      'Keep history',
      'Clear history',
    ])
    expect(document.activeElement).toBe(buttons[0]?.element)

    wrapper.unmount()
  })

  it('uses custom confirm and cancel labels for the batch flow', () => {
    const wrapper = mount(ConfirmDialog, {
      props: {
        message: 'Delete history for 5 items?\nThis removes every log entry.',
        confirmLabel: 'Delete 5 items',
        cancelLabel: 'Cancel',
      },
    })

    expect(wrapper.findAll('.dialog-actions button').map((b) => b.text())).toEqual(
      ['Cancel', 'Delete 5 items'],
    )
  })

  it('hides the detail line when the message is a single line', () => {
    const wrapper = mount(ConfirmDialog, { props: { message: 'Clear history?' } })

    expect(wrapper.find('.dialog-detail').exists()).toBe(false)
  })

  it('emits cancel from the cancel button, confirm from the danger button', () => {
    const wrapper = mount(ConfirmDialog, { props: { message: 'Clear history?' } })
    const buttons = wrapper.findAll('.dialog-actions button')

    buttons[0]?.trigger('click')
    buttons[1]?.trigger('click')

    expect(wrapper.emitted('cancel')).toEqual([[]])
    expect(wrapper.emitted('confirm')).toEqual([[]])
    expect(buttons[1]?.classes()).toContain('danger')
  })

  it('cancels on Escape and keeps focus cycling inside the dialog', async () => {
    const wrapper = mount(ConfirmDialog, {
      props: { message: 'Clear history?' },
      attachTo: document.body,
    })

    await wrapper.find('.overlay').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('cancel')).toEqual([[]])

    const buttons = wrapper.findAll('.dialog-actions button')
    ;(buttons[buttons.length - 1]?.element as HTMLButtonElement).focus()
    await buttons[buttons.length - 1]?.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(buttons[0]?.element)
    expect(wrapper.emitted('confirm')).toBeUndefined()

    wrapper.unmount()
  })

  it('cancels when the overlay itself is clicked, not the dialog', async () => {
    const wrapper = mount(ConfirmDialog, { props: { message: 'Clear history?' } })

    await wrapper.find('.overlay').trigger('click')
    expect(wrapper.emitted('cancel')).toEqual([[]])

    await wrapper.find('.dialog').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })
})
