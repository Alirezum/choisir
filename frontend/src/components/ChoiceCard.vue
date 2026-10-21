<script setup lang="ts">
import { ref, watch } from 'vue'

import { api } from '../api'
import type { PreviewModel } from '../types'
import ImageViewer from './ImageViewer.vue'

const props = defineProps<{
  item: string | null
  path: string
  preview: PreviewModel | null
}>()

const emit = defineEmits<{ open: [] }>()

const viewerIndex = ref<number | null>(null)

watch(
  () => props.preview,
  () => {
    viewerIndex.value = null
  },
)

function thumbUrl(index: number | null): string {
  return api.imageUrl(props.path, index, true)
}

function openViewer(index: number): void {
  viewerIndex.value = index
}

function closeViewer(): void {
  viewerIndex.value = null
}
</script>

<template>
  <div class="choice-card">
    <div class="choice-label">The choice</div>
    <button
      class="choice-name"
      :class="{ empty: item === null }"
      :disabled="item === null"
      :title="item === null ? '' : `Open ${item}`"
      @click="emit('open')"
    >
      {{ item ?? '— pick something —' }}
    </button>
  </div>
  <div class="preview-wrap">
    <div class="panel-label">Preview</div>
    <div class="preview-body">
      <pre class="preview">{{ preview?.text ?? '(preview appears here)' }}</pre>
      <div v-if="(preview?.images.length ?? 0) > 0" class="image-grid">
        <figure
          v-for="(image, index) in preview?.images ?? []"
          :key="`${image.index}-${image.name}`"
        >
          <button
            class="thumb-button"
            type="button"
            :aria-label="`View ${image.name}`"
            @click="openViewer(index)"
          >
            <img
              :src="thumbUrl(image.index)"
              :alt="image.name"
              loading="lazy"
              decoding="async"
            />
          </button>
          <figcaption :title="image.name">{{ image.name }}</figcaption>
        </figure>
      </div>
    </div>
  </div>
  <ImageViewer
    v-if="viewerIndex !== null && (preview?.images.length ?? 0) > 0"
    :images="preview?.images ?? []"
    :path="path"
    :start="viewerIndex"
    @close="closeViewer"
  />
</template>
