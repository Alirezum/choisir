import type { PickResponse, PreviewModel } from './api-contract.generated.ts'

export type {
  ArchiveResponse,
  BrowseResponse,
  BrowserEntry,
  ClearResponse,
  DefaultsResponse,
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

export interface StateQuery {
  path: string
  log_file?: string
  include_hidden?: boolean
  files_only?: boolean
  dirs_only?: boolean
}

export interface PickRequest {
  path: string
  log_file?: string | null
  seed?: number | null
  dry_run: boolean
  include_hidden: boolean
  files_only: boolean
  dirs_only: boolean
}

export interface RemoveHistoryItemsRequest {
  path: string
  log_file: string | null
  items: string[]
}
