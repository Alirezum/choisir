<script setup lang="ts">
import { computed } from 'vue'

import EmptyState from '../components/EmptyState.vue'
import PanelShell from '../components/PanelShell.vue'

const props = defineProps<{ items: string[]; total: number }>()

const header = computed(() => {
  if (props.items.length < props.total) {
    return `${props.total} remaining (showing the first ${props.items.length})`
  }
  return `${props.total} remaining`
})
</script>

<template>
  <PanelShell>
    <template #header>{{ header }}</template>
    <ul v-if="items.length > 0" class="list">
      <li v-for="name in items" :key="name" class="name-row" :title="name">
        {{ name }}
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
