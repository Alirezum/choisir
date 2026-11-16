<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import PanelShell from '../components/PanelShell.vue'

const props = defineProps<{ items: string[]; total: number }>()
const emit = defineEmits<{ skip: [name: string] }>()

function header(): string {
  if (props.items.length < props.total) {
    return `${props.total} remaining (showing the first ${props.items.length})`
  }
  return `${props.total} remaining`
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
    <EmptyState v-else>
      {{
        total === 0
          ? 'Everything in this folder has been picked.'
          : 'No items match the current options.'
      }}
    </EmptyState>
  </PanelShell>
</template>
