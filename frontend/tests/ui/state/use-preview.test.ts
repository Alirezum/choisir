import { nextTick, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { api } from '../../../src/api.ts'
import { usePreview } from '../../../src/state/use-preview.ts'
import type {
  PreviewImage,
  PreviewModel,
  PreviewVideo,
} from '../../../src/types.ts'
import { mountHost } from '../test-helpers.ts'

const image = (
  index: number | null,
  name = `image-${index ?? 'x'}.png`,
  size = 2048,
): PreviewImage => ({ index, name, media_type: 'image/png', size })

const video = (
  name = 'clip.mp4',
  mediaType = 'video/mp4',
  size = 3 * 1024 * 1024,
): PreviewVideo => ({ name, media_type: mediaType, size })

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

function setup(
  pathValue = '/tmp/choosier',
  initial: PreviewModel | null = null,
) {
  const path = ref(pathValue)
  const model = ref<PreviewModel | null>(initial)
  const { result, wrapper } = mountHost(() =>
    usePreview({ path: () => path.value, preview: () => model.value }),
  )
  return { path, model, preview: result, wrapper }
}

describe('usePreview', () => {
  it('renders no images or copy without a preview', () => {
    const { preview: unit, wrapper } = setup()

    expect(unit.images.value).toEqual([])
    expect(unit.showNumbers.value).toBe(false)
    expect(unit.imageLabel.value).toBe('')
    expect(unit.metaLine.value).toBe('')
    expect(unit.bodyText.value).toBe('')
    expect(unit.videoUrl.value).toBe(api.videoUrl('/tmp/choosier'))
    wrapper.unmount()
  })

  it('exposes the text body only when there is no media meta line', () => {
    const { preview: unit, wrapper } = setup(
      '/tmp/choosier',
      preview({ kind: 'text', text: 'hello world' }),
    )

    expect(unit.bodyText.value).toBe('hello world')
    expect(unit.metaLine.value).toBe('')
    wrapper.unmount()
  })

  it('labels a single image and builds the preview variant source', () => {
    const { preview: unit, wrapper } = setup(
      '/tmp/choosier',
      preview({
        kind: 'image',
        images: [image(0, 'only.png')],
        image_total: 1,
      }),
    )

    expect(unit.imageLabel.value).toBe('1 image')
    expect(unit.metaLine.value).toBe('PNG, 2.0 KB')
    expect(unit.bodyText.value).toBe('')
    expect(unit.images.value[0]?.src).toBe(
      api.imageUrl('/tmp/choosier', 0, 'preview'),
    )
    expect(unit.images.value[0]?.fullSrc).toBe(
      api.imageUrl('/tmp/choosier', 0),
    )
    wrapper.unmount()
  })

  it('labels multiple and truncated image sets with thumb sources', () => {
    const many = setup(
      '/tmp/choosier',
      preview({
        kind: 'image',
        images: [image(0), image(1), image(2)],
        image_total: 3,
      }),
    )
    expect(many.preview.imageLabel.value).toBe('3 images')
    expect(many.preview.images.value[1]?.src).toBe(
      api.imageUrl('/tmp/choosier', 1, 'thumb'),
    )
    many.wrapper.unmount()

    const truncated = setup(
      '/tmp/choosier',
      preview({
        kind: 'image',
        images: [image(0), image(1)],
        image_total: 40,
      }),
    )
    expect(truncated.preview.imageLabel.value).toBe('2 of 40 images')
    truncated.wrapper.unmount()
  })

  it('describes archives with and without images', () => {
    const withImages = setup(
      '/tmp/choosier',
      preview({ kind: 'archive', images: [image(0)], image_total: 1 }),
    )
    expect(withImages.preview.metaLine.value).toBe('Archive')
    withImages.wrapper.unmount()

    const withoutImages = setup(
      '/tmp/choosier',
      preview({ kind: 'archive', text: 'archive contents here' }),
    )
    expect(withoutImages.preview.metaLine.value).toBe('')
    expect(withoutImages.preview.bodyText.value).toBe('archive contents here')
    withoutImages.wrapper.unmount()
  })

  it('describes videos with the media label and size', () => {
    const { preview: unit, wrapper } = setup(
      '/tmp/choosier/clip.mov',
      preview({ kind: 'video', video: video('clip.mov', 'video/quicktime') }),
    )

    expect(unit.metaLine.value).toBe('MOV, 3.0 MB')
    expect(unit.videoUrl.value).toBe(
      api.videoUrl('/tmp/choosier/clip.mov'),
    )
    wrapper.unmount()
  })

  it('formats byte, kilobyte, and megabyte sizes at their boundaries', () => {
    const cases: Array<[number, string]> = [
      [1023, 'B'],
      [1024, 'KB'],
      [1024 * 1024, 'MB'],
    ]

    for (const [size, suffix] of cases) {
      const { preview: unit, wrapper } = setup(
        '/tmp/choosier',
        preview({ kind: 'image', images: [image(0, 'x.png', size)] }),
      )
      expect(unit.metaLine.value.endsWith(suffix)).toBe(true)
      if (suffix !== 'B') {
        expect(unit.metaLine.value).toContain('1.0')
      }
      wrapper.unmount()
    }
  })

  it('falls back to the subtype for unknown media types', () => {
    const { preview: unit, wrapper } = setup(
      '/tmp/choosier',
      preview({ kind: 'video', video: video('clip.flac', 'audio/x-flac', 10) }),
    )

    expect(unit.metaLine.value).toBe('X-FLAC, 10 B')
    wrapper.unmount()
  })

  it('shows frame numbers only when the preview supplies indexes', () => {
    const withoutIndexes = setup(
      '/tmp/choosier',
      preview({ kind: 'image', images: [image(null), image(null)] }),
    )
    expect(withoutIndexes.preview.showNumbers.value).toBe(false)
    withoutIndexes.wrapper.unmount()

    const withIndexes = setup(
      '/tmp/choosier',
      preview({ kind: 'image', images: [image(null), image(7)] }),
    )
    expect(withIndexes.preview.showNumbers.value).toBe(true)
    withIndexes.wrapper.unmount()
  })

  it('pads frame labels from the image index or the position', () => {
    const { preview: unit, wrapper } = setup()

    expect(unit.frameLabel(image(0), 3)).toBe('01')
    expect(unit.frameLabel(image(4), 0)).toBe('05')
    expect(unit.frameLabel(image(null), 9)).toBe('10')
    wrapper.unmount()
  })

  it('opens and closes the viewer with a reset on preview change', async () => {
    const { model, preview: unit, wrapper } = setup(
      '/tmp/choosier',
      preview({ kind: 'image', images: [image(0)] }),
    )

    unit.openViewer(2)
    expect(unit.viewerIndex.value).toBe(2)
    unit.reportVideoError()
    expect(unit.videoError.value).toBe(true)

    model.value = preview({ kind: 'text', text: 'next' })
    await nextTick()
    expect(unit.viewerIndex.value).toBeNull()
    expect(unit.videoError.value).toBe(false)

    unit.openViewer(0)
    unit.closeViewer()
    expect(unit.viewerIndex.value).toBeNull()
    wrapper.unmount()
  })

  it('omits the video source for a blank path', () => {
    const { preview: unit, wrapper } = setup('')

    expect(unit.videoUrl.value).toBe('')
    wrapper.unmount()
  })
})
