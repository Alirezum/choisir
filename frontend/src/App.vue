<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { api } from './api'
import BrowserPanel from './components/BrowserPanel.vue'
import ChoiceBoard from './components/ChoiceBoard.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import OptionsPanel from './components/OptionsPanel.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import RemainingPanel from './components/RemainingPanel.vue'
import StatusBar from './components/StatusBar.vue'
import type { PreviewModel, StateResponse } from './types'

const tabs = [
  { id: 'remaining', label: 'Remaining' },
  { id: 'history', label: 'History' },
  { id: 'browse', label: 'Browse' },
  { id: 'options', label: 'Options' },
] as const

type TabId = (typeof tabs)[number]['id']

const path = ref('')
const logFile = ref('')
const seed = ref('')
const dryRun = ref(false)
const includeHidden = ref(false)
const mode = ref<'all' | 'files' | 'dirs'>('all')

const choice = ref<{
  item: string
  path: string
  preview: PreviewModel | null
} | null>(null)
const status = ref('Choose a folder, then press Pick.')
const state = ref<StateResponse | null>(null)
const activeTab = ref<TabId>('remaining')
const clearing = ref(false)
const removingItem = ref<string | null>(null)
const removingHistory = ref(false)
const historyChecked = ref<string[]>([])
const pendingHistoryDelete = ref<string[] | null>(null)
const pickSerial = ref(0)
let previewSerial = 0
const pathInput = ref<HTMLInputElement | null>(null)

const historyDeleteCount = computed(() => pendingHistoryDelete.value?.length ?? 0)
const historyDeleteMessage = computed(() => {
  const count = historyDeleteCount.value
  if (count === 0) return ''
  const noun = count === 1 ? 'entry' : 'entries'
  return `Delete ${count} ${noun} from history?\nThis removes every log entry for the selected items, making them pickable again.`
})
const historyDeleteLabel = computed(() => {
  const count = historyDeleteCount.value
  return count === 1 ? 'Delete 1 item' : `Delete ${count} items`
})

const filters = computed(() => ({
  include_hidden: includeHidden.value,
  files_only: mode.value === 'files',
  dirs_only: mode.value === 'dirs',
}))

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function entryPath(item: string): string {
  const base = path.value.replace(/[/\\]+$/, '')
  return `${base}/${item}`
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
watch(path, () => {
  previewSerial += 1
  choice.value = null
  historyChecked.value = []
  pendingHistoryDelete.value = null
})
watch(logFile, () => {
  historyChecked.value = []
  pendingHistoryDelete.value = null
})

async function pick(): Promise<void> {
  if (path.value.trim() === '') {
    status.value = 'Enter a folder path.'
    pathInput.value?.focus()
    return
  }
  const rawSeed = seed.value.trim()
  let seedValue: number | null = null
  if (rawSeed !== '') {
    seedValue = Number(rawSeed)
    if (!Number.isInteger(seedValue)) {
      status.value = 'Seed must be a whole number.'
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
      status.value = "That folder doesn't exist."
    } else if (result.status === 'empty') {
      status.value = 'That folder has nothing to pick.'
    } else if (result.status === 'exhausted') {
      status.value = 'All items have been picked. Clear or archive history to start over.'
    } else {
      const item = result.item ?? ''
      previewSerial += 1
      choice.value = {
        item,
        path: entryPath(item),
        preview: result.preview,
      }
      pickSerial.value += 1
      status.value = result.logged
        ? `Picked ${item}.`
        : `Picked ${item}. Dry run, so it wasn't logged.`
    }
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
  }
}

async function openEntry(entry: string): Promise<void> {
  try {
    const result = await api.open(entry)
    status.value = `Opened ${result.opened}.`
  } catch (error) {
    status.value = describeError(error)
  }
}

async function openCurrent(): Promise<void> {
  if (choice.value === null) {
    status.value = 'Pick something first.'
    return
  }
  await openEntry(choice.value.path)
}

function openHistoryItem(item: string): void {
  void openEntry(entryPath(item))
}

async function previewHistoryItem(item: string): Promise<void> {
  const request = ++previewSerial
  const target = { item, path: entryPath(item), preview: null }
  choice.value = target
  try {
    const preview = await api.preview(target.path)
    if (request !== previewSerial) return
    choice.value = { ...target, preview }
    status.value = `Previewing ${item} from history.`
  } catch (error) {
    if (request !== previewSerial) return
    status.value = describeError(error)
  }
}

async function archiveHistory(): Promise<void> {
  try {
    const result = await api.archive(path.value, logFile.value)
    status.value =
      result.backup === null
        ? `No history file at ${result.log_file}.`
        : `Archived history to ${result.backup}.`
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
    historyChecked.value = []
  }
}

async function clearHistory(): Promise<void> {
  clearing.value = false
  try {
    const result = await api.clear(path.value, logFile.value)
    status.value = result.removed
      ? `Cleared ${result.log_file}.`
      : `No history file at ${result.log_file}.`
  } catch (error) {
    status.value = describeError(error)
  } finally {
    await refresh()
    historyChecked.value = []
  }
}

async function removeHistoryItem(item: string): Promise<void> {
  if (removingItem.value !== null) return
  removingItem.value = item
  try {
    const result = await api.removeHistoryItem(path.value, logFile.value, item)
    if (result.removed === 0) {
      status.value = `No history entry for "${item}".`
    } else if (result.removed === 1) {
      status.value = `Removed "${item}" from history.`
    } else {
      status.value = `Removed ${result.removed} entries for "${item}".`
    }
  } catch (error) {
    status.value = describeError(error)
  } finally {
    removingItem.value = null
    historyChecked.value = historyChecked.value.filter((name) => name !== item)
    await refresh()
  }
}

function toggleHistoryCheck(item: string): void {
  historyChecked.value = historyChecked.value.includes(item)
    ? historyChecked.value.filter((name) => name !== item)
    : [...historyChecked.value, item]
}

function addHistoryRange(items: string[]): void {
  historyChecked.value = [...new Set([...historyChecked.value, ...items])]
}

function toggleAllHistory(): void {
  const items = [
    ...new Set((state.value?.history ?? []).map((entry) => entry.item)),
  ]
  const allSelected =
    items.length > 0 &&
    items.every((item) => historyChecked.value.includes(item))
  historyChecked.value = allSelected ? [] : items
}

function requestDeleteSelected(): void {
  if (historyChecked.value.length === 0) return
  pendingHistoryDelete.value = [...historyChecked.value]
}

async function deleteSelectedHistory(): Promise<void> {
  const items = pendingHistoryDelete.value
  if (items === null) return
  pendingHistoryDelete.value = null
  removingHistory.value = true
  try {
    const result = await api.removeHistoryItems(path.value, logFile.value, items)
    if (result.removed === 0) {
      status.value = 'No matching history entries to remove.'
    } else if (result.removed === 1) {
      status.value = 'Removed 1 entry from history.'
    } else {
      status.value = `Removed ${result.removed} entries from history.`
    }
  } catch (error) {
    status.value = describeError(error)
  } finally {
    removingHistory.value = false
    historyChecked.value = historyChecked.value.filter(
      (item) => !items.includes(item),
    )
    await refresh()
  }
}

function onTabKey(event: KeyboardEvent, id: TabId): void {
  const current = tabs.findIndex((tab) => tab.id === id)
  let next = current
  if (event.key === 'ArrowRight') {
    next = (current + 1) % tabs.length
  } else if (event.key === 'ArrowLeft') {
    next = (current - 1 + tabs.length) % tabs.length
  } else if (event.key === 'Home') {
    next = 0
  } else if (event.key === 'End') {
    next = tabs.length - 1
  } else {
    return
  }
  event.preventDefault()
  const target = tabs[next]
  if (target === undefined) return
  activeTab.value = target.id
  void nextTick(() => document.getElementById(`tab-${target.id}`)?.focus())
}

function onKeydown(event: KeyboardEvent): void {
  if (!event.ctrlKey || event.key.toLowerCase() !== 'n') return
  event.preventDefault()
  if (
    clearing.value ||
    document.querySelector('.viewer-overlay, .overlay') !== null
  ) {
    return
  }
  void pick()
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
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.clearTimeout(refreshTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <span class="wordmark">choosier</span>
      <label class="location">
        <span class="sr-only">Folder</span>
        <input
          ref="pathInput"
          v-model="path"
          class="path-input"
          placeholder="Directory path"
          autocomplete="off"
          spellcheck="false"
          @keyup.enter="pick"
        />
      </label>
    </header>

    <main class="stage">
      <ChoiceBoard
        :item="choice?.item ?? null"
        :remaining="state?.remaining_total ?? 0"
        :picked="state?.history_total ?? 0"
        :serial="pickSerial"
        @pick="pick"
        @open="openCurrent"
      />

      <div class="workspace">
        <PreviewPanel
          :path="choice?.path ?? ''"
          :preview="choice?.preview ?? null"
        />

        <section class="side" aria-label="Folder panels">
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
              @click="activeTab = tab.id"
              @keydown="onTabKey($event, tab.id)"
            >
              {{ tab.label
              }}<span v-if="tabCount(tab.id) !== null" class="count">{{
                tabCount(tab.id)
              }}</span>
            </button>
          </nav>

          <div
            id="panel-remaining"
            v-show="activeTab === 'remaining'"
            class="tab-panel"
            role="tabpanel"
            aria-labelledby="tab-remaining"
            tabindex="0"
          >
            <RemainingPanel
              :items="state?.remaining ?? []"
              :total="state?.remaining_total ?? 0"
            />
          </div>

          <div
            id="panel-history"
            v-show="activeTab === 'history'"
            class="tab-panel"
            role="tabpanel"
            aria-labelledby="tab-history"
            tabindex="0"
          >
            <HistoryPanel
              :entries="state?.history ?? []"
              :total="state?.history_total ?? 0"
              :busy="removingItem !== null || removingHistory"
              :selected="choice?.item ?? null"
              :checked-items="historyChecked"
              @archive="archiveHistory"
              @clear="clearing = true"
              @remove="removeHistoryItem"
              @select="previewHistoryItem"
              @open="openHistoryItem"
              @toggle-check="toggleHistoryCheck"
              @range-check="addHistoryRange"
              @toggle-all="toggleAllHistory"
              @remove-selected="requestDeleteSelected"
            />
          </div>

          <div
            id="panel-browse"
            v-show="activeTab === 'browse'"
            class="tab-panel"
            role="tabpanel"
            aria-labelledby="tab-browse"
            tabindex="0"
          >
            <BrowserPanel v-model="path" />
          </div>

          <div
            id="panel-options"
            v-show="activeTab === 'options'"
            class="tab-panel"
            role="tabpanel"
            aria-labelledby="tab-options"
            tabindex="0"
          >
            <OptionsPanel
              v-model:log="logFile"
              v-model:seed="seed"
              v-model:dry="dryRun"
              v-model:hidden="includeHidden"
              v-model:mode="mode"
            />
          </div>
        </section>
      </div>
    </main>

    <StatusBar :message="status" />
  </div>

  <ConfirmDialog
    v-if="clearing"
    :message="`Clear history?\n${state?.log_file ?? path}`"
    @confirm="clearHistory"
    @cancel="clearing = false"
  />

  <ConfirmDialog
    v-if="pendingHistoryDelete !== null"
    :message="historyDeleteMessage"
    :confirm-label="historyDeleteLabel"
    cancel-label="Cancel"
    @confirm="deleteSelectedHistory"
    @cancel="pendingHistoryDelete = null"
  />
</template>
