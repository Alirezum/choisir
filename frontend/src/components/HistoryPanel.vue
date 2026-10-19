<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ lines: string[]; total: number }>()
const emit = defineEmits<{ archive: []; clear: [] }>()

const header = computed(() => {
  if (props.total === 0) return 'No history yet.'
  if (props.lines.length < props.total) {
    return `${props.total} logged (showing last ${props.lines.length})`
  }
  return `${props.total} logged`
})
</script>

<template>
  <div class="panel">
    <div class="panel-header">{{ header }}</div>
    <ul class="list">
      <li v-for="(line, index) in lines" :key="`${index}-${line}`" class="mono muted">
        {{ line }}
      </li>
    </ul>
    <div class="panel-actions">
      <button @click="emit('archive')">Archive history</button>
      <button class="danger" @click="emit('clear')">Clear history</button>
    </div>
  </div>
</template>
