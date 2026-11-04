import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { api } from '../../../src/api.ts'
import type { PreviewImage, PreviewModel } from '../../../src/types.ts'
import PreviewPanel from '../../../src/views/PreviewPanel.vue'

const image = (
  index: number | null,
  name = `image-${index ?? 'x'}.png`,
): PreviewImage => ({ index, name, media_type: 'image/png', size: 2048 })

const preview = (overrides: Partial<PreviewModel> = {}): PreviewModel => ({
  kind: 'text',
  text: '',
  truncated: false,
  entry_count: null,
  size: null,
  images: [],
  image_total: 0,
  video: null,
  ...overrides,
})

function mountPanel(
  overrides: Partial<{ path: string; preview: PreviewModel | null }> = {},
) {
  return mount(PreviewPanel, {
    props: {
      path: '/tmp/choosier',
      preview: preview({ text: 'hello' }),
      ...overrides,
    },
  })
}

describe('PreviewPanel', () => {
  it('renders the section head and the empty copy without a preview', () => {
    const wrapper = mountPanel({ preview: null })

    expect(wrapper.find('section').attributes('aria-label')).toBe('Preview')
    expect(wrapper.find('h2').text()).toBe('Preview')
    expect(wrapper.find('.section-meta').exists()).toBe(false)
    expect(wrapper.find('.empty-copy').text()).toBe(
      'Pick an item to preview it here.',
    )
  })

  it('renders the text body without a meta line', () => {
    const wrapper = mountPanel({
      preview: preview({ kind: 'text', text: 'first\nsecond' }),
    })

    expect(wrapper.find('.preview-meta').exists()).toBe(false)
    expect(wrapper.find('pre.preview').text()).toBe('first\nsecond')
    expect(wrapper.find('.image-grid').exists()).toBe(false)
    expect(wrapper.find('.video-frame').exists()).toBe(false)
  })

  it('renders the image label, meta line, and numbered grid', () => {
    const wrapper = mountPanel({
      preview: preview({
        kind: 'image',
        images: [image(0, 'a.png'), image(1, 'b.png')],
        image_total: 2,
      }),
    })

    expect(wrapper.find('.section-meta').text()).toBe('2 images')
    expect(wrapper.find('.preview-meta').text()).toBe('PNG, 2.0 KB')
    expect(wrapper.find('.image-grid').classes()).not.toContain('is-single')
    const frames = wrapper.findAll('.frame')
    expect(frames).toHaveLength(2)
    expect(frames[0]?.find('figcaption').text()).toBe('a.png')
    expect(frames[0]?.find('figcaption').attributes('title')).toBe('a.png')
    expect(frames[0]?.find('.frame-number').text()).toBe('01')
    expect(frames[1]?.find('.frame-number').text()).toBe('02')
    expect(frames[0]?.find('img').attributes('src')).toBe(
      api.imageUrl('/tmp/choosier', 0, 'thumb'),
    )
    expect(frames[0]?.find('img').attributes('alt')).toBe('a.png')
    expect(frames[0]?.find('.frame-button').attributes('aria-label')).toBe(
      'View a.png',
    )
  })

  it('marks a single image grid and uses the preview variant', () => {
    const wrapper = mountPanel({
      preview: preview({
        kind: 'image',
        images: [image(0, 'only.png')],
        image_total: 1,
      }),
    })

    expect(wrapper.find('.image-grid').classes()).toContain('is-single')
    expect(wrapper.find('.section-meta').text()).toBe('1 image')
    expect(wrapper.find('img').attributes('src')).toBe(
      api.imageUrl('/tmp/choosier', 0, 'preview'),
    )
  })

  it('omits frame numbers when the preview has no indexes', () => {
    const wrapper = mountPanel({
      preview: preview({
        kind: 'image',
        images: [image(null)],
        image_total: 1,
      }),
    })

    expect(wrapper.find('.frame-top').exists()).toBe(false)
  })

  it('renders the video frame with its label and fallback', async () => {
    const wrapper = mountPanel({
      path: '/tmp/choosier/clip.mp4',
      preview: preview({
        kind: 'video',
        video: { name: 'clip.mp4', media_type: 'video/mp4', size: 1024 },
      }),
    })

    expect(wrapper.find('.preview-meta').text()).toBe('MP4, 1.0 KB')
    const video = wrapper.find('video.preview-video')
    expect(video.attributes('src')).toBe(
      api.videoUrl('/tmp/choosier/clip.mp4'),
    )
    expect(video.attributes('aria-label')).toBe('Video preview of clip.mp4')
    expect(video.attributes('controls')).toBeDefined()
    expect(video.text()).toBe('This browser cannot play this video.')

    await video.trigger('error')
    expect(wrapper.find('video.preview-video').exists()).toBe(false)
    expect(wrapper.find('.video-fallback').text()).toBe(
      'Browser playback failed. Use Open above to play this file with your system player.',
    )
  })

  it('opens the viewer from a frame and closes it again', async () => {
    const wrapper = mountPanel({
      preview: preview({
        kind: 'image',
        images: [image(0, 'a.png'), image(1, 'b.png')],
        image_total: 2,
      }),
      attachTo: document.body,
    })

    expect(wrapper.find('.viewer-overlay').exists()).toBe(false)
    await wrapper.findAll('.frame-button')[1]?.trigger('click')

    const viewer = wrapper.find('.viewer-overlay')
    expect(viewer.exists()).toBe(true)
    expect(wrapper.find('.viewer-name').text()).toBe('b.png')
    expect(wrapper.find('.viewer-count').text()).toBe('2 / 2')

    await wrapper.find('.viewer-close').trigger('click')
    expect(wrapper.find('.viewer-overlay').exists()).toBe(false)

    wrapper.unmount()
  })
})
