import { nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { useImageViewer } from '../../../src/state/use-image-viewer.ts'
import type { ViewableImage } from '../../../src/view-models.ts'
import { mountHost } from '../test-helpers.ts'

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

function setup(
  images: ViewableImage[] = [viewable(0), viewable(1), viewable(2)],
  start = 0,
) {
  const list = ref(images)
  const close = vi.fn()
  const focusTarget = ref<HTMLButtonElement | null>(null)
  const { result, wrapper } = mountHost(() =>
    useImageViewer({
      images: () => list.value,
      start,
      close,
      focusTarget,
    }),
  )
  return { list, close, focusTarget, viewer: result, wrapper }
}

describe('useImageViewer', () => {
  it('starts at the requested index with the ready labels', () => {
    const { viewer, wrapper } = setup()

    expect(viewer.index.value).toBe(0)
    expect(viewer.current.value?.name).toBe('image-0.png')
    expect(viewer.counter.value).toBe('1 / 3')
    expect(viewer.zoomLabel.value).toBe('Fit')
    expect(viewer.imageStyle.value).toEqual({
      transform: 'translate(0px, 0px) scale(1)',
      cursor: 'default',
    })
    wrapper.unmount()
  })

  it('wraps navigation in both directions and ignores empty sets', () => {
    const { viewer, wrapper } = setup()

    viewer.step(-1)
    expect(viewer.index.value).toBe(2)
    viewer.step(1)
    expect(viewer.index.value).toBe(0)
    expect(viewer.current.value?.name).toBe('image-0.png')
    wrapper.unmount()

    const empty = setup([])
    empty.viewer.step(1)
    expect(empty.viewer.index.value).toBe(0)
    expect(empty.viewer.current.value).toBeNull()
    expect(empty.viewer.counter.value).toBe('1 / 0')
    empty.wrapper.unmount()
  })

  it('clamps zoom to the supported limits and labels each level', () => {
    const { viewer, wrapper } = setup()

    viewer.setZoom(0.5)
    expect(viewer.zoom.value).toBe(1)
    expect(viewer.zoomLabel.value).toBe('Fit')

    viewer.setZoom(2)
    expect(viewer.zoomLabel.value).toBe('200%')

    viewer.setZoom(99)
    expect(viewer.zoom.value).toBe(8)
    expect(viewer.zoomLabel.value).toBe('800%')
    wrapper.unmount()
  })

  it('steps through the zoom ladder and stops at the ends', () => {
    const { viewer, wrapper } = setup()

    viewer.stepZoom(1)
    expect(viewer.zoom.value).toBe(1.25)
    viewer.stepZoom(1)
    expect(viewer.zoom.value).toBe(1.5)
    viewer.stepZoom(-1)
    expect(viewer.zoom.value).toBe(1.25)
    viewer.stepZoom(-1)
    expect(viewer.zoom.value).toBe(1)

    viewer.setZoom(8)
    viewer.stepZoom(1)
    expect(viewer.zoom.value).toBe(8)
    wrapper.unmount()
  })

  it('resets and toggles zoom with the double-click level', () => {
    const { viewer, wrapper } = setup()

    viewer.setZoom(5)
    viewer.resetZoom()
    expect(viewer.zoom.value).toBe(1)

    viewer.toggleZoom()
    expect(viewer.zoom.value).toBe(2)
    viewer.toggleZoom()
    expect(viewer.zoom.value).toBe(1)
    wrapper.unmount()
  })

  it('ignores wheel events without a vertical delta', () => {
    const { viewer, wrapper } = setup()

    viewer.onWheel({ deltaY: 0 } as WheelEvent)
    expect(viewer.zoom.value).toBe(1)

    viewer.onWheel({ deltaY: -1 } as WheelEvent)
    expect(viewer.zoom.value).toBe(1.25)
    viewer.onWheel({ deltaY: 1 } as WheelEvent)
    expect(viewer.zoom.value).toBe(1)
    wrapper.unmount()
  })

  it('reports the dragging cursor and clamps pan offsets to the image box', () => {
    const { viewer, wrapper } = setup()
    const element = document.createElement('img')
    Object.defineProperty(element, 'clientWidth', { value: 100 })
    Object.defineProperty(element, 'clientHeight', { value: 200 })
    element.setPointerCapture = vi.fn()
    element.releasePointerCapture = vi.fn()
    viewer.imageEl.value = element

    viewer.onPointerDown({
      button: 0,
      clientX: 0,
      clientY: 0,
      pointerId: 1,
    } as PointerEvent)
    expect(viewer.dragging.value).toBe(false)
    expect(viewer.imageStyle.value.cursor).toBe('default')

    viewer.setZoom(2)
    expect(viewer.imageStyle.value.cursor).toBe('grab')
    viewer.onPointerDown({
      button: 0,
      clientX: 0,
      clientY: 0,
      pointerId: 1,
    } as PointerEvent)
    expect(viewer.dragging.value).toBe(true)
    expect(element.setPointerCapture).toHaveBeenCalledWith(1)
    expect(viewer.imageStyle.value.cursor).toBe('grabbing')

    viewer.onPointerMove({ clientX: 500, clientY: 500 } as PointerEvent)
    expect(viewer.offset.value).toEqual({ x: 50, y: 100 })
    viewer.onPointerMove({ clientX: -500, clientY: -500 } as PointerEvent)
    expect(viewer.offset.value).toEqual({ x: -50, y: -100 })

    viewer.onPointerUp({ pointerId: 1 } as PointerEvent)
    expect(viewer.dragging.value).toBe(false)
    expect(element.releasePointerCapture).toHaveBeenCalledWith(1)
    wrapper.unmount()
  })

  it('ignores non-primary buttons and right drags while fitted', () => {
    const { viewer, wrapper } = setup()

    viewer.setZoom(2)
    viewer.onPointerDown({
      button: 2,
      clientX: 0,
      clientY: 0,
      pointerId: 1,
    } as PointerEvent)
    expect(viewer.dragging.value).toBe(false)

    viewer.onPointerMove({ clientX: 10, clientY: 10 } as PointerEvent)
    expect(viewer.offset.value).toEqual({ x: 0, y: 0 })

    viewer.onPointerUp({ pointerId: 1 } as PointerEvent)
    expect(viewer.dragging.value).toBe(false)
    wrapper.unmount()
  })

  it('maps keyboard shortcuts to close, navigation, zoom, and reset', () => {
    const { viewer, close, wrapper } = setup()

    const handled = (key: string) =>
      ({
        key,
        preventDefault: vi.fn(),
      }) as unknown as KeyboardEvent

    viewer.onKeydown(handled('Escape'))
    expect(close).toHaveBeenCalledTimes(1)

    viewer.onKeydown(handled('ArrowLeft'))
    expect(viewer.index.value).toBe(2)
    viewer.onKeydown(handled('ArrowRight'))
    expect(viewer.index.value).toBe(0)

    const plus = handled('+')
    viewer.onKeydown(plus)
    expect(plus.preventDefault).toHaveBeenCalled()
    expect(viewer.zoom.value).toBe(1.25)
    const equals = handled('=')
    viewer.onKeydown(equals)
    expect(equals.preventDefault).toHaveBeenCalled()
    expect(viewer.zoom.value).toBe(1.5)
    const minus = handled('-')
    viewer.onKeydown(minus)
    expect(minus.preventDefault).toHaveBeenCalled()
    expect(viewer.zoom.value).toBe(1.25)
    const underscore = handled('_')
    viewer.onKeydown(underscore)
    expect(underscore.preventDefault).toHaveBeenCalled()
    expect(viewer.zoom.value).toBe(1)
    viewer.setZoom(3)
    const zero = handled('0')
    viewer.onKeydown(zero)
    expect(zero.preventDefault).toHaveBeenCalled()
    expect(viewer.zoom.value).toBe(1)

    const other = handled('x')
    viewer.onKeydown(other)
    expect(other.preventDefault).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('resets the zoom when stepping and preloads both neighbours', async () => {
    const created: string[] = []
    class FakeImage {
      set src(value: string) {
        created.push(value)
      }
    }
    vi.stubGlobal('Image', FakeImage)

    const { viewer, wrapper } = setup()
    created.length = 0

    viewer.setZoom(4)
    viewer.step(1)
    await nextTick()
    expect(viewer.zoom.value).toBe(1)
    expect(created).toEqual(['/media/full-0', '/media/full-2'])

    created.length = 0
    viewer.step(1)
    await nextTick()
    expect(created).toEqual(['/media/full-1', '/media/full-0'])
    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('skips preloading for a single image', () => {
    const created = vi.fn()
    class FakeImage {
      constructor() {
        created()
      }
    }
    vi.stubGlobal('Image', FakeImage)

    const { viewer, wrapper } = setup([viewable(0)])
    viewer.preload()
    expect(created).not.toHaveBeenCalled()

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('locks body scrolling, focuses the close target, and restores on unmount', () => {
    const focus = vi.fn()
    const focusTarget = ref<HTMLButtonElement | null>({
      focus,
    } as unknown as HTMLButtonElement)
    document.body.style.overflow = 'auto'
    const add = vi.spyOn(window, 'addEventListener')
    const remove = vi.spyOn(window, 'removeEventListener')

    const { wrapper } = mountHost(() =>
      useImageViewer({
        images: () => [viewable(0), viewable(1)],
        start: 0,
        close: vi.fn(),
        focusTarget,
      }),
    )

    expect(document.body.style.overflow).toBe('hidden')
    expect(focus).toHaveBeenCalled()
    expect(add).toHaveBeenCalledWith('keydown', expect.any(Function))

    wrapper.unmount()
    expect(document.body.style.overflow).toBe('auto')
    expect(remove).toHaveBeenCalledWith('keydown', expect.any(Function))
  })
})
