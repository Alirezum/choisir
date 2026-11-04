<script setup lang="ts">
import { ref } from 'vue'

import {
  MAX_ZOOM,
  MIN_ZOOM,
  useImageViewer,
} from '../state/use-image-viewer.ts'
import type { ViewableImage } from '../view-models.ts'

const props = defineProps<{
  images: ViewableImage[]
  start: number
}>()
const emit = defineEmits<{ close: [] }>()

const closeButton = ref<HTMLButtonElement | null>(null)

const {
  zoom,
  dragging,
  imageEl,
  current,
  counter,
  zoomLabel,
  imageStyle,
  step,
  stepZoom,
  resetZoom,
  toggleZoom,
  onWheel,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  close,
} = useImageViewer({
  images: () => props.images,
  start: props.start,
  close: () => emit('close'),
  focusTarget: closeButton,
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
      <div class="viewer-id">
        <span class="viewer-name" :title="current?.name ?? ''">
          {{ current?.name ?? '' }}
        </span>
        <span class="viewer-count">{{ counter }}</span>
      </div>
      <div class="viewer-controls">
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
          :href="current.fullSrc"
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
          <span class="viewer-close-text">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </header>
    <button
      v-if="images.length > 1"
      class="viewer-nav prev"
      type="button"
      aria-label="Previous image"
      @click="step(-1)"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M15 4L7 12l8 8" />
      </svg>
    </button>
    <img
      v-if="current"
      :ref="(el) => (imageEl = el as HTMLImageElement | null)"
      class="viewer-image"
      :class="{ dragging }"
      :style="imageStyle"
      :src="current.fullSrc"
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
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M9 4l8 8-8 8" />
      </svg>
    </button>
  </div>
</template>
