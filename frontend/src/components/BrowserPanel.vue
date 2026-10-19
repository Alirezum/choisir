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
  <div class="panel">
    <div class="panel-header mono path-line">
      {{ listing?.path ?? props.modelValue }}
    </div>
    <div v-if="error !== ''" class="panel-header error">{{ error }}</div>
    <ul v-else class="list">
      <li v-if="listing?.parent" class="row" @click="load(listing.parent)">
        <span class="mono">⬆ ..</span>
      </li>
      <li
        v-for="entry in listing?.entries ?? []"
        :key="entry.name"
        class="row"
        :class="{ muted: !entry.is_dir }"
        @click="navigate(entry)"
      >
        <span class="mono">{{ entry.is_dir ? '📁' : '📄' }} {{ entry.name }}</span>
      </li>
    </ul>
    <div class="panel-actions">
      <button class="primary" :disabled="listing === null" @click="useThisFolder">
        Use this folder
      </button>
    </div>
  </div>
</template>
