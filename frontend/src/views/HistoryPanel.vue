<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import PanelShell from '../components/PanelShell.vue'
import type { HistoryEntry } from '../types.ts'

const props = defineProps<{
  entries: HistoryEntry[]
  total: number
  busy: boolean
  selected: string | null
  checkedItems: string[]
  header: string
  allSelected: boolean
  checkedCount: number
}>()
const emit = defineEmits<{
  archive: []
  clear: []
  remove: [item: string]
  open: [item: string]
  select: [item: string, shift: boolean]
  toggleAll: []
  removeSelected: []
}>()

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

function rows() {
  const checked = new Set(props.checkedItems)
  return props.entries.map((entry, index) => ({
    ...entry,
    key: `${index}-${entry.timestamp ?? 'legacy'}-${entry.item}`,
    time: formatTimestamp(entry.timestamp),
    selected: entry.item === props.selected,
    checked: checked.has(entry.item),
  }))
}
</script>

<template>
  <PanelShell header-class="history-header">
    <template #header>
      <span>{{ header }}</span>
      <button
        v-if="rows().length > 0"
        class="panel-link"
        type="button"
        :disabled="busy"
        @click="emit('toggleAll')"
      >
        {{ allSelected ? 'Clear selection' : 'Select all' }}
      </button>
    </template>
    <p v-if="rows().length > 0" class="history-hint">
      Click a row to preview and select it. Shift-click to select a range.
    </p>
    <ul v-if="rows().length > 0" class="list history-list">
      <li v-for="row in rows()" :key="row.key">
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
            @click="emit('select', row.item, $event.shiftKey)"
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
    <EmptyState v-else>
      Picked items land here. Remove one to make it available again.
    </EmptyState>
    <template #actions>
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
    </template>
  </PanelShell>
</template>
