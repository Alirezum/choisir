<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ items: string[]; total: number }>()

const header = computed(() => {
  if (props.total === 0) return 'Nothing left to pick.'
  if (props.items.length < props.total) {
    return `${props.total} remaining (showing first ${props.items.length})`
  }
  return `${props.total} remaining`
})
</script>

<template>
  <div class="panel">
    <div class="panel-header">{{ header }}</div>
    <ul class="list">
      <li v-for="name in items" :key="name" class="mono">{{ name }}</li>
    </ul>
  </div>
</template>
