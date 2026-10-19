<script setup lang="ts">
import type { PreviewModel } from '../types'

defineProps<{ item: string | null; preview: PreviewModel | null }>()

const emit = defineEmits<{ open: [] }>()
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
    <pre class="preview">{{ preview?.text ?? '(preview appears here)' }}</pre>
  </div>
</template>
