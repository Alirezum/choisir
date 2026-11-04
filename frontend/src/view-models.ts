// Type-only contracts between the composition root, state units, views, and
// shared presentation blocks. This module has no runtime logic.
import type { ComputedRef, Ref } from 'vue'

import type {
  BrowseResponse,
  BrowserEntry,
  HistoryEntry,
  PreviewImage,
  PreviewModel,
  StateResponse,
} from './types.ts'

export type TabId = 'remaining' | 'history' | 'browse' | 'options'
export type Mode = 'all' | 'files' | 'dirs'

export interface PanelTab {
  id: TabId
  label: string
}

export interface Choice {
  item: string
  path: string
  preview: PreviewModel | null
}

export interface FilterSelection {
  include_hidden: boolean
  files_only: boolean
  dirs_only: boolean
}

/** A preview image plus the client-built URLs each presentation needs. */
export interface ViewableImage extends PreviewImage {
  /** Grid thumbnail, or the single-image preview variant. */
  src: string
  /** Full-size image used by the viewer and the original link. */
  fullSrc: string
}

export interface ChoiceBoardModel {
  item: string | null
  remaining: number
  picked: number
  serial: number
}

export interface PanelTabsModel {
  tabs: readonly PanelTab[]
  activeTab: TabId
  counts: Record<TabId, number | null>
}

export interface RemainingPanelModel {
  items: string[]
  total: number
}

export interface HistoryPanelModel {
  entries: HistoryEntry[]
  total: number
  busy: boolean
  selected: string | null
  checkedItems: string[]
  header: string
  allSelected: boolean
  checkedCount: number
}

export interface BrowserPanelModel {
  path: string
  listing: BrowseResponse | null
  error: string
}

export interface OptionsPanelModel {
  logFile: string
  seed: string
  dryRun: boolean
  includeHidden: boolean
  mode: Mode
}

export interface StatusBarModel {
  message: string
}

export interface ConfirmDialogModel {
  message: string
  confirmLabel?: string
  cancelLabel?: string
}

export interface PreviewPanelModel {
  path: string
  preview: PreviewModel | null
}

export interface ImageViewerModel {
  images: ViewableImage[]
  start: number
}

export interface PanelShellModel {
  headerClass?: string
}

/** Intent payloads emitted by views and handled by state units. */
export interface HistorySelectIntent {
  item: string
  shift: boolean
}

export interface HistoryItemIntent {
  item: string
}

export interface BrowserNavigateIntent {
  entry: BrowserEntry
}

export interface BrowserUseFolderIntent {
  path: string
}

export interface TabSelectIntent {
  id: TabId
}

export interface TabKeyIntent {
  event: KeyboardEvent
  id: TabId
}

/** The binding surface returned by use-workspace and consumed by App.vue. */
export interface WorkspaceBinding {
  pathInput: Ref<HTMLInputElement | null>
  tabs: readonly PanelTab[]

  path: Ref<string>
  logFile: Ref<string>
  seed: Ref<string>
  dryRun: Ref<boolean>
  includeHidden: Ref<boolean>
  mode: Ref<Mode>

  status: Ref<string>
  state: Ref<StateResponse | null>
  choice: Ref<Choice | null>
  pickSerial: Ref<number>
  activeTab: Ref<TabId>

  clearing: Ref<boolean>
  removingItem: Ref<string | null>
  removingHistory: Ref<boolean>
  historyChecked: Ref<string[]>
  historyHeader: ComputedRef<string>
  historyAllSelected: ComputedRef<boolean>
  historyCheckedCount: ComputedRef<number>
  pendingHistoryDelete: Ref<string[] | null>
  historyDeleteCount: ComputedRef<number>
  historyDeleteMessage: ComputedRef<string>
  historyDeleteLabel: ComputedRef<string>

  tabCount: (id: TabId) => number | null

  pick: () => Promise<void>
  openCurrent: () => Promise<void>
  openHistoryItem: (item: string) => void
  previewHistoryItem: (item: string) => Promise<void>
  archiveHistory: () => Promise<void>
  requestClear: () => void
  confirmClear: () => Promise<void>
  cancelClear: () => void
  removeHistoryItem: (item: string) => Promise<void>
  selectHistoryItem: (item: string, shift: boolean) => void
  toggleAllHistory: () => void
  requestDeleteSelected: () => void
  confirmDeleteSelected: () => Promise<void>
  cancelDeleteSelected: () => void
  onTabSelect: (id: TabId) => void
  onTabKey: (event: KeyboardEvent, id: TabId) => void
}
