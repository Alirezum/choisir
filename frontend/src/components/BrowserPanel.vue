<script setup lang="ts">
import { ref, watch } from 'vue'

import { api } from '../api'
import type { BrowseResponse, BrowserEntry } from '../types'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const listing = ref<BrowseResponse | null>(null)
const error = ref('')

async function load(target: string): Promise<void> {
  if (target.trim() === '') return
  try {
    listing.value = await api.browse(target)
    error.value = ''
  } catch (problem) {
    error.value = problem instanceof Error ? problem.message : String(problem)
    listing.value = null
  }
}

watch(() => props.modelValue, (value) => void load(value), { immediate: true })

function navigate(entry: BrowserEntry): void {
  if (!entry.is_dir || listing.value === null) return
  const base = listing.value.path.replace(/[/\\]+$/, '')
  void load(`${base}/${entry.name}`)
}

function useThisFolder(): void {
  if (listing.value !== null) {
    emit('update:modelValue', listing.value.path)
  }
}
</script>

<template>
  <div class="panel browser">
    <div class="panel-header path-line" :title="listing?.path ?? props.modelValue">
      {{ listing?.path ?? props.modelValue }}
    </div>
    <p v-if="error !== ''" class="panel-empty error">{{ error }}</p>
    <template v-else>
      <ul class="list browser-list">
        <li v-if="listing?.parent">
          <button
            class="browser-row"
            type="button"
            @click="load(listing.parent)"
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
            @click="navigate(entry)"
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
    <div class="panel-actions">
      <button
        class="primary"
        type="button"
        :disabled="listing === null"
        @click="useThisFolder"
      >
        Use this folder
      </button>
    </div>
  </div>
</template>
