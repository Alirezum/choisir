<script setup lang="ts">
import ImageViewer from '../components/ImageViewer.vue'
import { usePreview } from '../state/use-preview.ts'
import type { PreviewModel } from '../types.ts'

const props = defineProps<{
  path: string
  preview: PreviewModel | null
}>()

const {
  viewerIndex,
  videoError,
  images,
  showNumbers,
  imageLabel,
  metaLine,
  bodyText,
  videoUrl,
  frameLabel,
  openViewer,
  closeViewer,
  reportVideoError,
} = usePreview({
  path: () => props.path,
  preview: () => props.preview,
})
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
        <div v-if="preview.video !== null" class="video-frame">
          <video
            v-if="!videoError"
            class="preview-video"
            controls
            playsinline
            preload="metadata"
            :src="videoUrl"
            :aria-label="`Video preview of ${preview.video.name}`"
            @error="reportVideoError"
          >
            This browser cannot play this video.
          </video>
          <p v-else class="video-fallback">
            Browser playback failed. Use <strong>Open</strong> above to play
            this file with your system player.
          </p>
        </div>
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
                  :src="image.src"
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
