<script setup lang="ts">
import type { PanelTab, TabId } from '../view-models.ts'

defineProps<{
  tabs: readonly PanelTab[]
  activeTab: TabId
  counts: Record<TabId, number | null>
}>()
const emit = defineEmits<{
  select: [id: TabId]
  keydown: [event: KeyboardEvent, id: TabId]
}>()
</script>

<template>
  <nav class="tabs" role="tablist" aria-label="Folder panels">
    <button
      v-for="tab in tabs"
      :id="`tab-${tab.id}`"
      :key="tab.id"
      type="button"
      role="tab"
      :class="{ active: activeTab === tab.id }"
      :aria-selected="activeTab === tab.id"
      :aria-controls="`panel-${tab.id}`"
      :tabindex="activeTab === tab.id ? 0 : -1"
      @click="emit('select', tab.id)"
      @keydown="emit('keydown', $event, tab.id)"
    >
      {{ tab.label
      }}<span v-if="counts[tab.id] !== null" class="count">{{
        counts[tab.id]
      }}</span>
    </button>
  </nav>
</template>
