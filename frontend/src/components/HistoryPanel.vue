<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { HistoryEntry } from '../types'

const props = defineProps<{
  entries: HistoryEntry[]
  total: number
  busy: boolean
  selected: string | null
  checkedItems: string[]
}>()
const emit = defineEmits<{
  archive: []
  clear: []
  remove: [item: string]
  select: [item: string]
  open: [item: string]
  toggleCheck: [item: string]
  rangeCheck: [items: string[]]
  toggleAll: []
  removeSelected: []
}>()

const anchor = ref<string | null>(null)

const header = computed(() => {
  if (props.entries.length < props.total) {
    return `${props.total} picked (showing the last ${props.entries.length})`
  }
  return `${props.total} picked`
})

const checkedCount = computed(() => props.checkedItems.length)

const allSelected = computed(() => {
  if (props.entries.length === 0) return false
  const checked = new Set(props.checkedItems)
  return props.entries.every((entry) => checked.has(entry.item))
})

watch(
  () => props.entries,
  (entries) => {
    if (
      anchor.value !== null &&
      !entries.some((entry) => entry.item === anchor.value)
    ) {
      anchor.value = null
    }
  },
)

watch(
  () => props.checkedItems.length,
  (count) => {
    if (count === 0) anchor.value = null
  },
)

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

const rows = computed(() => {
  const checked = new Set(props.checkedItems)
  return props.entries.map((entry, index) => ({
    ...entry,
    key: `${index}-${entry.timestamp ?? 'legacy'}-${entry.item}`,
    time: formatTimestamp(entry.timestamp),
    selected: entry.item === props.selected,
    checked: checked.has(entry.item),
  }))
})

function namesInRange(from: string, to: string): string[] {
  const names = props.entries.map((entry) => entry.item)
  const start = names.indexOf(from)
  const end = names.indexOf(to)
  if (start === -1 || end === -1) return [to]
  return names.slice(Math.min(start, end), Math.max(start, end) + 1)
}

function selectRange(item: string): void {
  if (props.busy) return
  if (anchor.value === null) {
    anchor.value = item
    emit('rangeCheck', [item])
    return
  }
  emit('rangeCheck', namesInRange(anchor.value, item))
}

function onRowClick(item: string, event: MouseEvent): void {
  if (props.busy) return
  if (event.shiftKey) {
    event.preventDefault()
    selectRange(item)
    return
  }
  anchor.value = item
  emit('toggleCheck', item)
  emit('select', item)
}

function onToggleAll(): void {
  anchor.value = null
  emit('toggleAll')
}
</script>

<template>
  <div class="panel">
    <div class="panel-header history-header">
      <span>{{ header }}</span>
      <button
        v-if="rows.length > 0"
        class="panel-link"
        type="button"
        :disabled="busy"
        @click="onToggleAll"
      >
        {{ allSelected ? 'Clear selection' : 'Select all' }}
      </button>
    </div>
    <p v-if="rows.length > 0" class="history-hint">
      Click a row to preview and select it. Shift-click to select a range.
    </p>
    <ul v-if="rows.length > 0" class="list history-list">
      <li v-for="row in rows" :key="row.key">
        <div
          class="history-row"
          :class="{ 'is-selected': row.selected, 'is-checked': row.checked }"
        >
          <button
            class="history-select"
            type="button"
            :aria-label="`Preview and select ${row.item}`"
            :aria-pressed="row.checked ? 'true' : 'false'"
            :aria-current="row.selected ? 'true' : undefined"
            :title="`Preview and select ${row.item}`"
            @click="onRowClick(row.item, $event)"
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
            :disabled="busy"
            @click.stop="emit('open', row.item)"
          >
            ↗
          </button>
          <button
            class="history-delete"
            type="button"
            :aria-label="`Remove ${row.item} from history`"
            title="Remove from history (it becomes pickable again)"
            :disabled="busy"
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
      <button
        v-if="checkedCount > 0"
        class="danger"
        type="button"
        :disabled="busy"
        @click="emit('removeSelected')"
      >
        Delete selected ({{ checkedCount }})
      </button>
      <button type="button" :disabled="busy" @click="emit('archive')">
        Archive history
      </button>
      <button
        class="danger"
        type="button"
        :disabled="busy"
        @click="emit('clear')"
      >
        Clear history
      </button>
    </div>
  </div>
</template>
