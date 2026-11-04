<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ items: string[]; total: number }>()

const header = computed(() => {
  if (props.items.length < props.total) {
    return `${props.total} remaining (showing the first ${props.items.length})`
  }
  return `${props.total} remaining`
})
</script>

<template>
  <div class="panel">
    <div class="panel-header">{{ header }}</div>
    <ul v-if="items.length > 0" class="list">
      <li v-for="name in items" :key="name" class="name-row" :title="name">
        {{ name }}
      </li>
    </ul>
    <p v-else class="panel-empty">
      {{
        total === 0
          ? 'Everything in this folder has been picked.'
          : 'No items match the current options.'
      }}
    </p>
  </div>
</template>
