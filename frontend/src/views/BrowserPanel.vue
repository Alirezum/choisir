<script setup lang="ts">
import EmptyState from '../components/EmptyState.vue'
import PanelShell from '../components/PanelShell.vue'
import type { BrowseResponse, BrowserEntry } from '../types.ts'

const props = defineProps<{
  path: string
  listing: BrowseResponse | null
  error: string
}>()
const emit = defineEmits<{
  navigate: [target: BrowserEntry | string]
  useFolder: []
}>()
</script>

<template>
  <PanelShell
    class="browser"
    header-class="path-line"
    :header-title="props.listing?.path ?? props.path"
  >
    <template #header>{{ props.listing?.path ?? props.path }}</template>
    <EmptyState v-if="error !== ''" class="error">{{ error }}</EmptyState>
    <template v-else>
      <ul class="list browser-list">
        <li v-if="listing?.parent">
          <button
            class="browser-row"
            type="button"
            @click="emit('navigate', listing.parent)"
          >
            <svg
              class="row-icon"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M8 12.5V4.5" />
              <path d="M4.5 8L8 4.5 11.5 8" />
            </svg>
            <span class="browser-name">Parent folder</span>
          </button>
        </li>
        <li v-for="entry in listing?.entries ?? []" :key="entry.name">
          <button
            v-if="entry.is_dir"
            class="browser-row"
            type="button"
            :title="`Open ${entry.name}`"
            @click="emit('navigate', entry)"
          >
            <svg
              class="row-icon"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M2.5 4.5h4l1.2 1.5h5.8v6.5h-11z" />
            </svg>
            <span class="browser-name">{{ entry.name }}</span>
            <svg
              class="browser-chevron"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M6 3.5L10.5 8 6 12.5" />
            </svg>
          </button>
          <div v-else class="browser-row is-file" :title="entry.name">
            <svg
              class="row-icon"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M4 2.5h5l3 3v8H4z" />
              <path d="M9 2.5v3h3" />
            </svg>
            <span class="browser-name">{{ entry.name }}</span>
          </div>
        </li>
        <li
          v-if="listing !== null && listing.entries.length === 0"
          class="browser-empty"
        >
          This folder is empty.
        </li>
      </ul>
    </template>
    <template #actions>
      <button
        class="primary"
        type="button"
        :disabled="listing === null"
        @click="emit('useFolder')"
      >
        Use this folder
      </button>
    </template>
  </PanelShell>
</template>
