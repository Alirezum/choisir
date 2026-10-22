<script setup lang="ts">
import { computed } from 'vue'

const MAX_FLAPS = 48

const props = defineProps<{
  item: string | null
  remaining: number
  picked: number
  serial: number
}>()

const emit = defineEmits<{ pick: []; open: [] }>()

const characters = computed(() => {
  if (props.item === null) return []
  const parts = Array.from(props.item)
  if (parts.length <= MAX_FLAPS) return parts
  return [...parts.slice(0, MAX_FLAPS - 1), '…']
})

const emptyTitle = computed(() => {
  if (props.remaining > 0) return 'Nothing picked yet'
  return props.picked > 0 ? 'All picked' : 'Nothing to pick'
})

const emptyMeta = computed(() => {
  if (props.remaining > 0) return 'Press Pick to choose the first one.'
  return props.picked > 0
    ? 'Clear or archive history to start over.'
    : 'This folder is empty.'
})
</script>

<template>
  <section class="board" aria-label="Pick result">
    <div class="board-surface">
      <h2 class="sr-only">
        {{ item === null ? 'No item picked yet' : `Picked ${item}` }}
      </h2>
      <div
        v-if="item !== null"
        :key="`${item}-${serial}`"
        class="flaps"
        :title="item"
      >
        <span
          v-for="(character, index) in characters"
          :key="index"
          class="flap"
          :class="{ 'is-space': character === ' ' }"
          :style="{ animationDelay: `${Math.min(index, 20) * 14}ms` }"
          aria-hidden="true"
        >
          {{ character === ' ' ? '' : character }}
        </span>
      </div>
      <div v-else class="board-empty">
        <p class="board-empty-title">{{ emptyTitle }}</p>
        <p class="board-empty-meta">{{ emptyMeta }}</p>
      </div>
      <div class="board-meta">
        <span class="board-stat"><strong>{{ remaining }}</strong> remaining</span>
        <span class="board-divider" aria-hidden="true"></span>
        <span class="board-stat"><strong>{{ picked }}</strong> picked</span>
        <button
          v-if="item !== null"
          class="board-open"
          type="button"
          @click="emit('open')"
        >
          Open
        </button>
      </div>
    </div>
    <button
      class="pick-lever"
      type="button"
      aria-keyshortcuts="Control+N"
      @click="emit('pick')"
    >
      <span class="pick-title">Pick</span>
      <span class="pick-hint" aria-hidden="true">
        <kbd>Ctrl</kbd><kbd>N</kbd>
      </span>
    </button>
  </section>
</template>
