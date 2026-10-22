<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { api } from '../api'
import type { PreviewImage, PreviewModel } from '../types'
import ImageViewer from './ImageViewer.vue'

const props = defineProps<{
  path: string
  preview: PreviewModel | null
}>()

const viewerIndex = ref<number | null>(null)

const images = computed(() => props.preview?.images ?? [])
const showNumbers = computed(() =>
  images.value.some((image) => image.index !== null),
)
const imageLabel = computed(() => {
  if (images.value.length === 0) return ''
  const total = props.preview?.image_total ?? images.value.length
  if (total > images.value.length) {
    return `${images.value.length} of ${total} images`
  }
  return total === 1 ? '1 image' : `${total} images`
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function mediaLabel(mediaType: string): string {
  return (mediaType.split('/')[1] ?? mediaType).toUpperCase()
}

const metaLine = computed(() => {
  const preview = props.preview
  if (preview === null) return ''
  if (preview.kind === 'image' && preview.images[0] !== undefined) {
    const image = preview.images[0]
    return `${mediaLabel(image.media_type)}, ${formatSize(image.size)}`
  }
  if (preview.kind === 'archive' && preview.images.length > 0) {
    return 'Archive'
  }
  return ''
})

const bodyText = computed(() => {
  const preview = props.preview
  if (preview === null || metaLine.value !== '') return ''
  return preview.text
})

watch(
  () => props.preview,
  () => {
    viewerIndex.value = null
  },
)

function previewImageUrl(index: number | null): string {
  return api.imageUrl(
    props.path,
    index,
    images.value.length === 1 ? 'preview' : 'thumb',
  )
}

function frameLabel(image: PreviewImage, index: number): string {
  return String((image.index ?? index) + 1).padStart(2, '0')
}

function openViewer(index: number): void {
  viewerIndex.value = index
}

function closeViewer(): void {
  viewerIndex.value = null
}
</script>

<template>
  <section class="preview-panel" aria-label="Preview">
    <header class="section-head">
      <h2>Preview</h2>
      <span v-if="imageLabel !== ''" class="section-meta">{{ imageLabel }}</span>
    </header>
    <div class="preview-body">
      <template v-if="preview !== null">
        <p v-if="metaLine !== ''" class="preview-meta">{{ metaLine }}</p>
        <pre v-if="bodyText !== ''" class="preview">{{ bodyText }}</pre>
        <div
          v-if="images.length > 0"
          class="image-grid"
          :class="{ 'is-single': images.length === 1 }"
        >
          <figure
            v-for="(image, index) in images"
            :key="`${image.index}-${image.name}`"
            class="frame"
          >
            <button
              class="frame-button"
              type="button"
              :aria-label="`View ${image.name}`"
              :title="`View ${image.name}`"
              @click="openViewer(index)"
            >
              <span v-if="showNumbers" class="frame-top">
                <span class="frame-number">{{ frameLabel(image, index) }}</span>
              </span>
              <span class="frame-shot">
                <img
                  :src="previewImageUrl(image.index)"
                  :alt="image.name"
                  loading="lazy"
                  decoding="async"
                />
              </span>
            </button>
            <figcaption :title="image.name">{{ image.name }}</figcaption>
          </figure>
        </div>
      </template>
      <p v-else class="empty-copy">Pick an item to preview it here.</p>
    </div>
    <ImageViewer
      v-if="viewerIndex !== null && images.length > 0"
      :images="images"
      :path="path"
      :start="viewerIndex"
      @close="closeViewer"
    />
  </section>
</template>
