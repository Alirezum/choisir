<script setup lang="ts">
import { computed } from 'vue'

import type { HistoryEntry } from '../types'

const props = defineProps<{
  entries: HistoryEntry[]
  total: number
  busyItem: string | null
}>()
const emit = defineEmits<{ archive: []; clear: []; remove: [item: string] }>()

const header = computed(() => {
  if (props.total === 0) return 'No history yet.'
  if (props.entries.length < props.total) {
    return `${props.total} logged (showing last ${props.entries.length})`
  }
  return `${props.total} logged`
})
</script>

<template>
  <div class="panel">
    <div class="panel-header">{{ header }}</div>
    <ul class="list">
      <li
        v-for="(entry, index) in entries"
        :key="`${index}-${entry.display}`"
        class="history-row mono muted"
      >
        <span class="history-text" :title="entry.display">{{ entry.display }}</span>
        <button
          class="history-delete"
          type="button"
          :aria-label="`Remove ${entry.item} from history`"
          title="Remove from history (item becomes pickable again)"
          :disabled="busyItem !== null"
          @click="emit('remove', entry.item)"
        >
          ✕
        </button>
      </li>
    </ul>
    <div class="panel-actions">
      <button @click="emit('archive')">Archive history</button>
      <button class="danger" @click="emit('clear')">Clear history</button>
    </div>
  </div>
</template>
