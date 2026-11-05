<script setup lang="ts">
import PanelShell from '../components/PanelShell.vue'
import type { FilterPanelModel } from '../view-models.ts'

defineProps<{ filterPanel: FilterPanelModel }>()

const emit = defineEmits<{
  toggleType: [key: string]
  toggleEntry: [name: string]
  selectAllTypes: []
  clearTypes: []
  selectAllEntries: []
  clearEntries: []
  clearFilters: []
}>()

const logFile = defineModel<string>('log', { required: true })
const seed = defineModel<string>('seed', { required: true })
const dryRun = defineModel<boolean>('dry', { required: true })
const includeHidden = defineModel<boolean>('hidden', { required: true })
const mode = defineModel<'all' | 'files' | 'dirs'>('mode', { required: true })
</script>

<template>
  <PanelShell class="options-panel">
    <template #header>Changes apply to the next pick.</template>
    <div class="options-body">
      <label class="field">
        <span>Log file</span>
        <input
          v-model="logFile"
          placeholder="empty = &lt;directory&gt;/.choosier.jsonl"
        />
      </label>
      <label class="field">
        <span>Seed</span>
        <input v-model="seed" placeholder="empty = random" />
      </label>
      <label class="check">
        <input v-model="dryRun" type="checkbox" />
        Dry run (nothing is logged)
      </label>
      <label class="check">
        <input v-model="includeHidden" type="checkbox" />
        Include hidden items
      </label>
      <fieldset class="mode">
        <legend>Mode</legend>
        <label><input v-model="mode" type="radio" value="all" /> Files and folders</label>
        <label><input v-model="mode" type="radio" value="files" /> Files only</label>
        <label><input v-model="mode" type="radio" value="dirs" /> Folders only</label>
      </fieldset>

      <section class="filter-section" aria-label="Filters">
        <p id="filter-summary" class="filter-summary" aria-live="polite">
          {{
            filterPanel.ready
              ? filterPanel.summary
              : 'Choose a folder to see filter options.'
          }}
        </p>

        <template v-if="filterPanel.ready && filterPanel.validPath && !filterPanel.empty">
          <fieldset class="filter-group">
            <legend>Types</legend>
            <div class="filter-actions">
              <button type="button" @click="emit('selectAllTypes')">
                Select all types
              </button>
              <button type="button" @click="emit('clearTypes')">Clear types</button>
            </div>
            <ul class="filter-list" aria-describedby="filter-summary">
              <li v-for="type in filterPanel.types" :key="type.key">
                <label class="filter-row">
                  <input
                    type="checkbox"
                    :checked="filterPanel.checkedTypeKeys.has(type.key)"
                    @change="emit('toggleType', type.key)"
                  />
                  <span class="filter-name" :title="type.label">{{ type.label }}</span>
                  <span class="filter-meta">{{ type.count }}</span>
                </label>
              </li>
            </ul>
          </fieldset>

          <fieldset class="filter-group">
            <legend>Entries</legend>
            <div class="filter-actions">
              <button type="button" @click="emit('selectAllEntries')">
                Select all entries
              </button>
              <button type="button" @click="emit('clearEntries')">
                Clear selection
              </button>
            </div>
            <ul
              class="filter-list"
              :aria-describedby="
                filterPanel.entriesTruncated
                  ? 'filter-summary filter-notice'
                  : 'filter-summary'
              "
            >
              <li v-for="entry in filterPanel.entries" :key="entry.name">
                <label class="filter-row">
                  <input
                    type="checkbox"
                    :checked="filterPanel.checkedEntryNames.has(entry.name)"
                    @change="emit('toggleEntry', entry.name)"
                  />
                  <span class="filter-name" :title="entry.name">{{ entry.name }}</span>
                  <span class="filter-meta">{{ entry.typeLabel }}</span>
                </label>
              </li>
            </ul>
            <p
              v-if="filterPanel.entriesTruncated"
              id="filter-notice"
              class="filter-notice"
            >
              Showing first {{ filterPanel.entries.length }} of
              {{ filterPanel.entriesTotal }} entries. Select all and Clear
              selection apply to these visible entries. Entries outside this
              list are unchanged here; type filters still apply to them.
            </p>
          </fieldset>
        </template>

        <button
          type="button"
          class="filter-clear"
          :disabled="!filterPanel.active"
          @click="emit('clearFilters')"
        >
          Clear filters
        </button>
      </section>
    </div>
  </PanelShell>
</template>
