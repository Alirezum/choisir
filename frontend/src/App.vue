<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { api } from './api'
import BrowserPanel from './components/BrowserPanel.vue'
import ChoiceCard from './components/ChoiceCard.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import OptionsPanel from './components/OptionsPanel.vue'
import RemainingPanel from './components/RemainingPanel.vue'
import StatusBar from './components/StatusBar.vue'
import type { PreviewModel, StateResponse } from './types'

const tabs = [
  { id: 'browse', label: 'Browse' },
  { id: 'remaining', label: 'Remaining' },
  { id: 'history', label: 'History' },
  { id: 'options', label: 'Options' },
] as const

type TabId = (typeof tabs)[number]['id']

const path = ref('')
const logFile = ref('')
const seed = ref('')
const dryRun = ref(false)
const includeHidden = ref(false)
const mode = ref<'all' | 'files' | 'dirs'>('all')

const choice = ref<{ item: string; preview: PreviewModel | null } | null>(null)
const status = ref('Enter a directory and press Pick.')
const state = ref<StateResponse | null>(null)
const activeTab = ref<TabId>('remaining')
const clearing = ref(false)
const pathInput = ref<HTMLInputElement | null>(null)

const filters = computed(() => ({
  include_hidden: includeHidden.value,
  files_only: mode.value === 'files',
  dirs_only: mode.value === 'dirs',
}))

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function tabCount(id: TabId): number | null {
  if (state.value === null) return null
  if (id === 'remaining') return state.value.remaining_total
  if (id === 'history') return state.value.history_total
  return null
}

async function refresh(): Promise<void> {
  if (path.value.trim() === '') {
    state.value = null
    return
  }
  try {
    state.value = await api.state({
      path: path.value,
      log_file: logFile.value,
      ...filters.value,
    })
  } catch (error) {
    status.value = describeError(error)
  }
}

let refreshTimer: number | undefined

function scheduleRefresh(): void {
  window.clearTimeout(refreshTimer)
  refreshTimer = window.setTimeout(() => void refresh(), 250)
}

watch([path, logFile, includeHidden, mode], scheduleRefresh)

async function pick(): Promise<void> {
  if (path.value.trim() === '') {
    status.value = 'Enter a directory.'
    pathInput.value?.focus()
    return
  }
  const rawSeed = seed.value.trim()
  let seedValue: number | null = null
  if (rawSeed !== '') {
    seedValue = Number(rawSeed)
    if (!Number.isInteger(seedValue)) {
      status.value = 'Invalid seed (must be an integer).'
      return
    }
  }
  try {
    const result = await api.pick({
      path: path.value,
      log_file: logFile.value === '' ? null : logFile.value,
      seed: seedValue,
      dry_run: dryRun.value,
      ...filters.value,
    })
    if (result.status === 'invalid_path') {
      status.value = 'Invalid Path.'
    } else if (result.status === 'empty') {
      status.value = 'Path Empty.'
    } else if (result.status === 'exhausted') {
      status.value = 'All choices have been selected. Delete log to reset.'
    } else {
      choice.value = { item: result.item ?? '', preview: result.preview }
      status.value = result.logged
        ? `Logged in ${result.log_file}.`
        : 'Dry run: selection not logged.'
    }
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
  }
}

async function openCurrent(): Promise<void> {
  if (choice.value === null) {
    status.value = 'Pick something first.'
    return
  }
  const base = path.value.replace(/[/\\]+$/, '')
  try {
    const result = await api.open(`${base}/${choice.value.item}`)
    status.value = `Opened ${result.opened}.`
  } catch (error) {
    status.value = describeError(error)
  }
}

async function archiveHistory(): Promise<void> {
  try {
    const result = await api.archive(path.value, logFile.value)
    status.value =
      result.backup === null
        ? `No log at ${result.log_file}.`
        : `Archived to ${result.backup}.`
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
  }
}

async function clearHistory(): Promise<void> {
  clearing.value = false
  try {
    const result = await api.clear(path.value, logFile.value)
    status.value = result.removed
      ? `Removed ${result.log_file}.`
      : `No log at ${result.log_file}.`
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.ctrlKey && event.key.toLowerCase() === 'n') {
    event.preventDefault()
    void pick()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    const defaults = await api.defaults()
    path.value = defaults.path
    logFile.value = defaults.log_file
  } catch (error) {
    status.value = describeError(error)
  }
  await refresh()
  pathInput.value?.focus()
  pathInput.value?.select()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.clearTimeout(refreshTimer)
})
</script>

<template>
  <header class="topbar">
    <h1>choosier</h1>
    <span class="tag">local web UI</span>
  </header>
  <div class="pathbar">
    <input
      ref="pathInput"
      v-model="path"
      class="path-input"
      placeholder="Directory path"
      @keyup.enter="pick"
    />
    <button class="primary" @click="pick">Pick<kbd>ctrl+n</kbd></button>
    <button :disabled="choice === null" @click="openCurrent">Open</button>
  </div>
  <main>
    <section class="left">
      <ChoiceCard
        :item="choice?.item ?? null"
        :preview="choice?.preview ?? null"
        @open="openCurrent"
      />
      <StatusBar :message="status" />
    </section>
    <section class="right">
      <nav class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label
          }}<span v-if="tabCount(tab.id) !== null" class="count">{{
            tabCount(tab.id)
          }}</span>
        </button>
      </nav>
      <BrowserPanel v-show="activeTab === 'browse'" v-model="path" />
      <RemainingPanel
        v-show="activeTab === 'remaining'"
        :items="state?.remaining ?? []"
        :total="state?.remaining_total ?? 0"
      />
      <HistoryPanel
        v-show="activeTab === 'history'"
        :lines="state?.history ?? []"
        :total="state?.history_total ?? 0"
        @archive="archiveHistory"
        @clear="clearing = true"
      />
      <OptionsPanel
        v-show="activeTab === 'options'"
        v-model:log="logFile"
        v-model:seed="seed"
        v-model:dry="dryRun"
        v-model:hidden="includeHidden"
        v-model:mode="mode"
      />
    </section>
  </main>
  <ConfirmDialog
    v-if="clearing"
    :message="`Clear all history?\n${state?.log_file ?? path}`"
    @confirm="clearHistory"
    @cancel="clearing = false"
  />
</template>
