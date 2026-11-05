import type { PickResponse, PreviewModel } from './api-contract.generated.ts'

export type {
  ArchiveResponse,
  BrowseResponse,
  BrowserEntry,
  ClearResponse,
  DefaultsResponse,
  FilterEntryOption,
  FilterOptions,
  FilterTypeOption,
  FilteredStateResponse,
  HistoryEntry,
  OpenResponse,
  PickResponse,
  PreviewImage,
  PreviewModel,
  PreviewVideo,
  RemoveHistoryItemResponse,
  RemoveHistoryItemsResponse,
  StateResponse,
} from './api-contract.generated.ts'

export type PreviewKind = PreviewModel['kind']

export type PickStatus = PickResponse['status']

/** The existing folder options that shape a pick. */
export interface FolderFlags {
  include_hidden: boolean
  files_only: boolean
  dirs_only: boolean
}

/** Session-only type and entry exclusions sent with state and pick requests. */
export interface FilterExclusions {
  excluded_types: string[]
  excluded_entries: string[]
}

export interface StateQuery {
  path: string
  log_file?: string
  include_hidden?: boolean
  files_only?: boolean
  dirs_only?: boolean
}

export interface FilteredStateRequest extends FolderFlags {
  path: string
  log_file?: string | null
  excluded_types?: string[]
  excluded_entries?: string[]
}

export interface PickRequest extends FolderFlags {
  path: string
  log_file?: string | null
  seed?: number | null
  dry_run: boolean
  excluded_types?: string[]
  excluded_entries?: string[]
}

export interface RemoveHistoryItemsRequest {
  path: string
  log_file: string | null
  items: string[]
}
