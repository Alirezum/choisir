<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import PanelShell from '../components/PanelShell.vue'
import type { SkippedRow } from '../view-models.ts'

const props = defineProps<{
  items: string[]
  total: number
  skipped: readonly SkippedRow[]
  skippedTotal: number
  allSkipped: boolean
}>()
const emit = defineEmits<{
  skip: [name: string]
  restore: [name: string]
  'restore-all': []
}>()

function header(): string {
  if (props.items.length < props.total) {
    return `${props.total} remaining (showing the first ${props.items.length})`
  }
  return `${props.total} remaining`
}

function emptyMessage(): string {
  if (props.allSkipped) {
    return 'Every available item is skipped. Restore skipped items to pick again.'
  }
  if (props.total === 0 && props.skippedTotal > 0) {
    return 'No items are available right now.'
  }
  if (props.total === 0) {
    return 'Everything in this folder has been picked.'
  }
  return 'No items match the current options.'
}
</script>

<template>
  <PanelShell>
    <template #header>{{ header() }}</template>
    <ul v-if="items.length > 0" class="list">
      <li v-for="name in items" :key="name" class="name-row" :title="name">
        <span class="name">{{ name }}</span>
        <button
          type="button"
          class="skip-button"
          :aria-label="'Skip ' + name"
          @click="emit('skip', name)"
          @keydown.enter.prevent="emit('skip', name)"
        >
          Not now
        </button>
      </li>
    </ul>
    <EmptyState v-else>{{ emptyMessage() }}</EmptyState>

    <section class="skipped-section" aria-label="Skipped items">
      <h3 class="skipped-heading">Skipped</h3>
      <ul v-if="skipped.length > 0" class="list skipped-list">
        <li
          v-for="row in skipped"
          :key="row.name"
          class="skipped-row"
          :title="row.name"
        >
          <span class="skipped-text">
            {{ row.name }} — returns in {{ row.returnsIn }}
          </span>
          <button
            type="button"
            class="restore-button"
            :aria-label="`Restore ${row.name}, returns in ${row.returnsIn}`"
            @click="emit('restore', row.name)"
          >
            Restore
          </button>
        </li>
      </ul>
      <button
        type="button"
        class="restore-all"
        aria-label="Restore all skipped items"
        :disabled="skippedTotal === 0"
        @click="emit('restore-all')"
      >
        Restore all
      </button>
    </section>
  </PanelShell>
</template>
