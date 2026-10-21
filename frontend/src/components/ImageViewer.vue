<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { api } from '../api'
import type { PreviewImage } from '../types'

const MIN_ZOOM = 1
const MAX_ZOOM = 8
const ZOOM_LEVELS = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8]
const DOUBLE_CLICK_ZOOM = 2

const props = defineProps<{
  images: PreviewImage[]
  path: string
  start: number
}>()

const emit = defineEmits<{ close: [] }>()

const index = ref(props.start)
const zoom = ref(MIN_ZOOM)
const offset = ref({ x: 0, y: 0 })
const dragging = ref(false)
const imageEl = ref<HTMLImageElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
let previousOverflow = ''
let dragStart = { x: 0, y: 0, offsetX: 0, offsetY: 0 }

const current = computed<PreviewImage | null>(
  () => props.images[index.value] ?? null,
)
const counter = computed(() => `${index.value + 1} / ${props.images.length}`)
const zoomLabel = computed(() =>
  zoom.value === MIN_ZOOM ? 'Fit' : `${Math.round(zoom.value * 100)}%`,
)
const imageStyle = computed(() => ({
  transform: `translate(${offset.value.x}px, ${offset.value.y}px) scale(${zoom.value})`,
  cursor:
    zoom.value > MIN_ZOOM ? (dragging.value ? 'grabbing' : 'grab') : 'default',
}))

function close(): void {
  emit('close')
}

function step(delta: number): void {
  const total = props.images.length
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

function imageUrl(image: PreviewImage): string {
  return api.imageUrl(props.path, image.index)
}

function preload(): void {
  const total = props.images.length
  if (total < 2) return
  for (const offsetStep of [-1, 1]) {
    const image = props.images[(index.value + offsetStep + total) % total]
    if (image !== undefined) {
      const loader = new Image()
      loader.src = imageUrl(image)
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
  closeButton.value?.focus()
  preload()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = previousOverflow
})
</script>

<template>
  <div
    class="viewer-overlay"
    role="dialog"
    aria-modal="true"
    :aria-label="current?.name ?? 'Image viewer'"
    @wheel.prevent="onWheel"
    @click.self="close"
  >
    <header class="viewer-top">
      <span class="viewer-name" :title="current?.name ?? ''">
        {{ current?.name ?? '' }}
      </span>
      <span class="viewer-count">{{ counter }}</span>
      <div class="viewer-zoom" role="group" aria-label="Zoom">
        <button
          class="viewer-zoom-out"
          type="button"
          aria-label="Zoom out"
          title="Zoom out (-)"
          :disabled="zoom <= MIN_ZOOM"
          @click="stepZoom(-1)"
        >
          −
        </button>
        <button
          class="viewer-zoom-label"
          type="button"
          aria-label="Reset zoom to fit"
          title="Reset zoom (0)"
          @click="resetZoom"
        >
          {{ zoomLabel }}
        </button>
        <button
          class="viewer-zoom-in"
          type="button"
          aria-label="Zoom in"
          title="Zoom in (+)"
          :disabled="zoom >= MAX_ZOOM"
          @click="stepZoom(1)"
        >
          +
        </button>
      </div>
      <a
        v-if="current"
        class="viewer-link"
        :href="imageUrl(current)"
        target="_blank"
        rel="noopener"
      >
        Open original
      </a>
      <button
        ref="closeButton"
        class="viewer-close"
        type="button"
        aria-label="Close viewer"
        @click="close"
      >
        ✕
      </button>
    </header>
    <button
      v-if="images.length > 1"
      class="viewer-nav prev"
      type="button"
      aria-label="Previous image"
      @click="step(-1)"
    >
      ‹
    </button>
    <img
      v-if="current"
      ref="imageEl"
      class="viewer-image"
      :class="{ dragging }"
      :style="imageStyle"
      :src="imageUrl(current)"
      :alt="current.name"
      draggable="false"
      @dblclick.stop="toggleZoom"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    />
    <button
      v-if="images.length > 1"
      class="viewer-nav next"
      type="button"
      aria-label="Next image"
      @click="step(1)"
    >
      ›
    </button>
  </div>
</template>
