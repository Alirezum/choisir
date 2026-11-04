import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'

import type { ViewableImage } from '../view-models.ts'

export const MIN_ZOOM = 1
export const MAX_ZOOM = 8
const ZOOM_LEVELS = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8]
const DOUBLE_CLICK_ZOOM = 2

export interface ImageViewerDeps {
  images: () => ViewableImage[]
  start: number
  close: () => void
  focusTarget?: Ref<HTMLButtonElement | null>
}

export interface ImageViewerBinding {
  MIN_ZOOM: number
  MAX_ZOOM: number
  index: Ref<number>
  zoom: Ref<number>
  offset: Ref<{ x: number; y: number }>
  dragging: Ref<boolean>
  imageEl: Ref<HTMLImageElement | null>
  current: ComputedRef<ViewableImage | null>
  counter: ComputedRef<string>
  zoomLabel: ComputedRef<string>
  imageStyle: ComputedRef<{ transform: string; cursor: string }>
  step: (delta: number) => void
  stepZoom: (direction: 1 | -1) => void
  setZoom: (value: number) => void
  resetZoom: () => void
  toggleZoom: () => void
  onWheel: (event: WheelEvent) => void
  onPointerDown: (event: PointerEvent) => void
  onPointerMove: (event: PointerEvent) => void
  onPointerUp: (event: PointerEvent) => void
  onKeydown: (event: KeyboardEvent) => void
  preload: () => void
  close: () => void
}

/**
 * View-local unit for the image viewer: index wrap, zoom ladder and limits,
 * pan clamping, pointer capture, keyboard/wheel handling, neighbour preload,
 * and the body-scroll lock. Media addresses come ready-made on `fullSrc`.
 */
export function useImageViewer(deps: ImageViewerDeps): ImageViewerBinding {
  const index = ref(deps.start)
  const zoom = ref(MIN_ZOOM)
  const offset = ref({ x: 0, y: 0 })
  const dragging = ref(false)
  const imageEl = ref<HTMLImageElement | null>(null)
  let previousOverflow = ''
  let dragStart = { x: 0, y: 0, offsetX: 0, offsetY: 0 }

  const current = computed<ViewableImage | null>(
    () => deps.images()[index.value] ?? null,
  )
  const counter = computed(() => `${index.value + 1} / ${deps.images().length}`)
  const zoomLabel = computed(() =>
    zoom.value === MIN_ZOOM ? 'Fit' : `${Math.round(zoom.value * 100)}%`,
  )
  const imageStyle = computed(() => ({
    transform: `translate(${offset.value.x}px, ${offset.value.y}px) scale(${zoom.value})`,
    cursor:
      zoom.value > MIN_ZOOM ? (dragging.value ? 'grabbing' : 'grab') : 'default',
  }))

  function close(): void {
    deps.close()
  }

  function step(delta: number): void {
    const total = deps.images().length
    if (total === 0) return
    index.value = (index.value + delta + total) % total
  }

  function clampOffsets(): void {
    const element = imageEl.value
    if (element === null || zoom.value <= MIN_ZOOM) {
      offset.value = { x: 0, y: 0 }
      return
    }
    const maxX = (element.clientWidth * (zoom.value - 1)) / 2
    const maxY = (element.clientHeight * (zoom.value - 1)) / 2
    offset.value = {
      x: Math.max(-maxX, Math.min(maxX, offset.value.x)),
      y: Math.max(-maxY, Math.min(maxY, offset.value.y)),
    }
  }

  function setZoom(value: number): void {
    zoom.value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value))
    clampOffsets()
  }

  function stepZoom(direction: 1 | -1): void {
    if (direction > 0) {
      const next = ZOOM_LEVELS.find((level) => level > zoom.value + 0.001)
      setZoom(next ?? MAX_ZOOM)
    } else {
      let next = MIN_ZOOM
      for (const level of ZOOM_LEVELS) {
        if (level < zoom.value - 0.001) {
          next = level
        }
      }
      setZoom(next)
    }
  }

  function resetZoom(): void {
    setZoom(MIN_ZOOM)
  }

  function toggleZoom(): void {
    setZoom(zoom.value === MIN_ZOOM ? DOUBLE_CLICK_ZOOM : MIN_ZOOM)
  }

  function onWheel(event: WheelEvent): void {
    if (event.deltaY === 0) return
    stepZoom(event.deltaY < 0 ? 1 : -1)
  }

  function onPointerDown(event: PointerEvent): void {
    if (zoom.value <= MIN_ZOOM || event.button !== 0) return
    dragging.value = true
    dragStart = {
      x: event.clientX,
      y: event.clientY,
      offsetX: offset.value.x,
      offsetY: offset.value.y,
    }
    imageEl.value?.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: PointerEvent): void {
    if (!dragging.value) return
    offset.value = {
      x: dragStart.offsetX + (event.clientX - dragStart.x),
      y: dragStart.offsetY + (event.clientY - dragStart.y),
    }
    clampOffsets()
  }

  function onPointerUp(event: PointerEvent): void {
    if (!dragging.value) return
    dragging.value = false
    imageEl.value?.releasePointerCapture(event.pointerId)
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      close()
    } else if (event.key === 'ArrowLeft') {
      step(-1)
    } else if (event.key === 'ArrowRight') {
      step(1)
    } else if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      stepZoom(1)
    } else if (event.key === '-' || event.key === '_') {
      event.preventDefault()
      stepZoom(-1)
    } else if (event.key === '0') {
      event.preventDefault()
      resetZoom()
    }
  }

  function preload(): void {
    const images = deps.images()
    if (images.length < 2) return
    for (const offsetStep of [-1, 1]) {
      const image = images[(index.value + offsetStep + images.length) % images.length]
      if (image !== undefined) {
        const loader = new Image()
        loader.src = image.fullSrc
      }
    }
  }

  watch(index, () => {
    resetZoom()
    preload()
  })

  onMounted(() => {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeydown)
    deps.focusTarget?.value?.focus()
    preload()
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = previousOverflow
  })

  return {
    MIN_ZOOM,
    MAX_ZOOM,
    index,
    zoom,
    offset,
    dragging,
    imageEl,
    current,
    counter,
    zoomLabel,
    imageStyle,
    step,
    stepZoom,
    setZoom,
    resetZoom,
    toggleZoom,
    onWheel,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onKeydown,
    preload,
    close,
  }
}
