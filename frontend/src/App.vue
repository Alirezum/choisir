<script setup lang="ts">
import BrowserPanel from './views/BrowserPanel.vue'
import ChoiceBoard from './views/ChoiceBoard.vue'
import ConfirmDialog from './views/ConfirmDialog.vue'
import HistoryPanel from './views/HistoryPanel.vue'
import OptionsPanel from './views/OptionsPanel.vue'
import PreviewPanel from './views/PreviewPanel.vue'
import RemainingPanel from './views/RemainingPanel.vue'
import PanelTabs from './views/PanelTabs.vue'
import StatusBar from './views/StatusBar.vue'
import { useWorkspace } from './state/use-workspace'

const {
  pathInput,
  tabs,

  path,
  logFile,
  seed,
  dryRun,
  includeHidden,
  mode,

  status,
  state,
  choice,
  pickSerial,
  activeTab,

  filterPanel,

  clearing,
  removingItem,
  removingHistory,
  historyChecked,
  historyHeader,
  historyAllSelected,
  historyCheckedCount,
  pendingHistoryDelete,
  clearMessage,
  historyDeleteMessage,
  historyDeleteLabel,

  browserListing,
  browserError,
  tabCounts,

  pick,
  openCurrent,
  openHistoryItem,
  archiveHistory,
  requestClear,
  confirmClear,
  cancelClear,
  removeHistoryItem,
  selectHistoryItem,
  toggleAllHistory,
  requestDeleteSelected,
  confirmDeleteSelected,
  cancelDeleteSelected,
  onTabSelect,
  onTabKey,
  navigateBrowser,
  useBrowserFolder,

  toggleFilterType,
  toggleFilterEntry,
  selectAllFilterTypes,
  clearFilterTypes,
  selectAllFilterEntries,
  clearFilterEntries,
  clearFilters,
} = useWorkspace()

// The template's `ref="pathInput"` writes into this binding; the picker unit
// owns focusing it after a blank-path validation failure.
void pathInput
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
          <PanelTabs
            :tabs="tabs"
            :active-tab="activeTab"
            :counts="tabCounts"
            @select="onTabSelect"
            @keydown="onTabKey"
          />

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
              :header="historyHeader"
              :all-selected="historyAllSelected"
              :checked-count="historyCheckedCount"
              @archive="archiveHistory"
              @clear="requestClear"
              @remove="removeHistoryItem"
              @select="selectHistoryItem"
              @open="openHistoryItem"
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
            <BrowserPanel
              :path="path"
              :listing="browserListing"
              :error="browserError"
              @navigate="navigateBrowser"
              @use-folder="useBrowserFolder"
            />
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
              :filter-panel="filterPanel"
              @toggle-type="toggleFilterType"
              @toggle-entry="toggleFilterEntry"
              @select-all-types="selectAllFilterTypes"
              @clear-types="clearFilterTypes"
              @select-all-entries="selectAllFilterEntries"
              @clear-entries="clearFilterEntries"
              @clear-filters="clearFilters"
            />
          </div>
        </section>
      </div>
    </main>

    <StatusBar :message="status" />
  </div>

  <ConfirmDialog
    v-if="clearing"
    :message="clearMessage"
    @confirm="confirmClear"
    @cancel="cancelClear"
  />

  <ConfirmDialog
    v-if="pendingHistoryDelete !== null"
    :message="historyDeleteMessage"
    :confirm-label="historyDeleteLabel"
    cancel-label="Cancel"
    @confirm="confirmDeleteSelected"
    @cancel="cancelDeleteSelected"
  />
</template>
