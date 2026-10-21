<script setup lang="ts">
import { api } from '../api'
import type { PreviewModel } from '../types'

const props = defineProps<{
  item: string | null
  path: string
  preview: PreviewModel | null
}>()

const emit = defineEmits<{ open: [] }>()

function imageUrl(index: number | null): string {
  return api.imageUrl(props.path, index)
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
          v-for="image in preview?.images ?? []"
          :key="`${image.index}-${image.name}`"
        >
          <a :href="imageUrl(image.index)" target="_blank" rel="noopener">
            <img
              :src="imageUrl(image.index)"
              :alt="image.name"
              loading="lazy"
              decoding="async"
            />
          </a>
          <figcaption :title="image.name">{{ image.name }}</figcaption>
        </figure>
      </div>
    </div>
  </div>
</template>
