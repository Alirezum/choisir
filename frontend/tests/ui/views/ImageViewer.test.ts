import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { ViewableImage } from '../../../src/view-models.ts'
import ImageViewer from '../../../src/views/ImageViewer.vue'

const viewable = (
  index: number,
  name = `image-${index}.png`,
): ViewableImage => ({
  index,
  name,
  media_type: 'image/png',
  size: 1024,
  src: `/media/thumb-${index}`,
  fullSrc: `/media/full-${index}`,
})

const images = [viewable(0, 'a.png'), viewable(1, 'b.png')]

function mountViewer(
  overrides: Partial<{ images: ViewableImage[]; start: number }> = {},
) {
  return mount(ImageViewer, {
    props: { images, start: 0, ...overrides },
    attachTo: document.body,
  })
}

describe('ImageViewer', () => {
  it('renders the overlay identity and the full-size image', () => {
    const wrapper = mountViewer()

    const overlay = wrapper.find('.viewer-overlay')
    expect(overlay.attributes('role')).toBe('dialog')
    expect(overlay.attributes('aria-modal')).toBe('true')
    expect(overlay.attributes('aria-label')).toBe('a.png')
    expect(wrapper.find('.viewer-name').text()).toBe('a.png')
    expect(wrapper.find('.viewer-name').attributes('title')).toBe('a.png')
    expect(wrapper.find('.viewer-count').text()).toBe('1 / 2')
    expect(wrapper.find('.viewer-image').attributes('src')).toBe(
      '/media/full-0',
    )
    expect(wrapper.find('.viewer-image').attributes('alt')).toBe('a.png')
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('Fit')
    expect(wrapper.find('.viewer-link').attributes('href')).toBe('/media/full-0')
    expect(wrapper.find('.viewer-link').attributes('target')).toBe('_blank')

    wrapper.unmount()
  })

  it('omits navigation arrows for a single image', () => {
    const wrapper = mountViewer({ images: [viewable(0)], start: 0 })

    expect(wrapper.find('.viewer-nav').exists()).toBe(false)

    wrapper.unmount()
  })

  it('steps through images with wrapping arrows', async () => {
    const wrapper = mountViewer()

    await wrapper.find('.viewer-nav.next').trigger('click')
    expect(wrapper.find('.viewer-name').text()).toBe('b.png')
    expect(wrapper.find('.viewer-count').text()).toBe('2 / 2')
    expect(wrapper.find('.viewer-image').attributes('src')).toBe(
      '/media/full-1',
    )

    await wrapper.find('.viewer-nav.next').trigger('click')
    expect(wrapper.find('.viewer-count').text()).toBe('1 / 2')

    await wrapper.find('.viewer-nav.prev').trigger('click')
    expect(wrapper.find('.viewer-count').text()).toBe('2 / 2')

    wrapper.unmount()
  })

  it('zooms with the controls, resets by label, and disables the ends', async () => {
    const wrapper = mountViewer()

    const zoomOut = wrapper.find('.viewer-zoom-out')
    const zoomIn = wrapper.find('.viewer-zoom-in')
    expect(zoomOut.attributes('disabled')).toBeDefined()
    expect(zoomIn.attributes('disabled')).toBeUndefined()

    await zoomIn.trigger('click')
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('125%')
    expect(zoomOut.attributes('disabled')).toBeUndefined()

    await wrapper.find('.viewer-zoom-label').trigger('click')
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('Fit')

    for (let step = 0; step < 12; step += 1) {
      await zoomIn.trigger('click')
    }
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('800%')
    expect(zoomIn.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.viewer-image').attributes('style')).toContain(
      'scale(8)',
    )

    wrapper.unmount()
  })

  it('toggles zoom on double click', async () => {
    const wrapper = mountViewer()
    const image = wrapper.find('.viewer-image')

    await image.trigger('dblclick')
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('200%')

    await image.trigger('dblclick')
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('Fit')

    wrapper.unmount()
  })

  it('emits close from the button, the overlay, and Escape', async () => {
    const button = mountViewer()
    await button.find('.viewer-close').trigger('click')
    expect(button.emitted('close')).toEqual([[]])
    button.unmount()

    const overlay = mountViewer()
    await overlay.find('.viewer-overlay').trigger('click')
    expect(overlay.emitted('close')).toEqual([[]])
    overlay.unmount()

    const escape = mountViewer()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(escape.emitted('close')).toEqual([[]])
    escape.unmount()
  })

  it('navigates and zooms from the keyboard', async () => {
    const wrapper = mountViewer()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.viewer-count').text()).toBe('2 / 2')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: '+' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('125%')

    window.dispatchEvent(new KeyboardEvent('keydown', { key: '0' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.viewer-zoom-label').text()).toBe('Fit')

    wrapper.unmount()
  })

  it('locks body scrolling while open and restores it on unmount', () => {
    document.body.style.overflow = 'scroll'

    const wrapper = mountViewer()
    expect(document.body.style.overflow).toBe('hidden')

    wrapper.unmount()
    expect(document.body.style.overflow).toBe('scroll')
  })
})
