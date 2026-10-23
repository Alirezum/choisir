<script setup lang="ts">
import { computed } from 'vue'

import type { HistoryEntry } from '../types'

const props = defineProps<{
  entries: HistoryEntry[]
  total: number
  busyItem: string | null
  selected: string | null
}>()
const emit = defineEmits<{
  archive: []
  clear: []
  remove: [item: string]
  select: [item: string]
  open: [item: string]
}>()

const header = computed(() => {
  if (props.entries.length < props.total) {
    return `${props.total} picked (showing the last ${props.entries.length})`
  }
  return `${props.total} picked`
})

function formatTimestamp(timestamp: string | null): string {
  if (timestamp === null) return ''
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''
  const today = new Date()
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

const rows = computed(() =>
  props.entries.map((entry, index) => ({
    ...entry,
    key: `${index}-${entry.timestamp ?? 'legacy'}-${entry.item}`,
    time: formatTimestamp(entry.timestamp),
    selected: entry.item === props.selected,
  })),
)
</script>

<template>
  <div class="panel">
    <div class="panel-header">{{ header }}</div>
    <ul v-if="rows.length > 0" class="list history-list">
      <li v-for="row in rows" :key="row.key">
        <div class="history-row" :class="{ 'is-selected': row.selected }">
          <button
            class="history-select"
            type="button"
            :aria-label="`Preview ${row.item}`"
            :aria-current="row.selected ? 'true' : undefined"
            :title="`Preview ${row.item}`"
            @click="emit('select', row.item)"
          >
            <time
              v-if="row.time !== ''"
              class="history-time"
              :datetime="row.timestamp ?? undefined"
            >
              {{ row.time }}
            </time>
            <span v-else class="history-time" aria-hidden="true"></span>
            <span class="history-text">{{ row.item }}</span>
          </button>
          <button
            class="history-open"
            type="button"
            :aria-label="`Open ${row.item} with the default program`"
            title="Open with the default program"
            @click.stop="emit('open', row.item)"
          >
            ↗
          </button>
          <button
            class="history-delete"
            type="button"
            :aria-label="`Remove ${row.item} from history`"
            title="Remove from history (it becomes pickable again)"
            :disabled="busyItem !== null"
            @click.stop="emit('remove', row.item)"
          >
            ×
          </button>
        </div>
      </li>
    </ul>
    <p v-else class="panel-empty">
      Picked items land here. Remove one to make it available again.
    </p>
    <div class="panel-actions">
      <button type="button" @click="emit('archive')">Archive history</button>
      <button class="danger" type="button" @click="emit('clear')">
        Clear history
      </button>
    </div>
  </div>
</template>
