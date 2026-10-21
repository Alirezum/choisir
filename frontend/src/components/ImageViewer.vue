<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { api } from '../api'
import type { PreviewImage } from '../types'

const props = defineProps<{
  images: PreviewImage[]
  path: string
  start: number
}>()

const emit = defineEmits<{ close: [] }>()

const index = ref(props.start)
const closeButton = ref<HTMLButtonElement | null>(null)
let previousOverflow = ''

const current = computed<PreviewImage | null>(
  () => props.images[index.value] ?? null,
)
const counter = computed(() => `${index.value + 1} / ${props.images.length}`)

function close(): void {
  emit('close')
}

function step(delta: number): void {
  const total = props.images.length
  if (total === 0) return
  index.value = (index.value + delta + total) % total
}

function imageUrl(image: PreviewImage): string {
  return api.imageUrl(props.path, image.index)
}

function preload(): void {
  const total = props.images.length
  if (total < 2) return
  for (const offset of [-1, 1]) {
    const image = props.images[(index.value + offset + total) % total]
    if (image !== undefined) {
      const loader = new Image()
      loader.src = imageUrl(image)
    }
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    close()
  } else if (event.key === 'ArrowLeft') {
    step(-1)
  } else if (event.key === 'ArrowRight') {
    step(1)
  }
}

watch(index, preload)

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
    @click.self="close"
  >
    <header class="viewer-top">
      <span class="viewer-name" :title="current?.name ?? ''">
        {{ current?.name ?? '' }}
      </span>
      <span class="viewer-count">{{ counter }}</span>
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
      class="viewer-image"
      :src="imageUrl(current)"
      :alt="current.name"
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
