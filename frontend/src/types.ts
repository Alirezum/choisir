export interface DefaultsResponse {
  path: string
  log_file: string
}

export interface BrowserEntry {
  name: string
  is_dir: boolean
}

export interface BrowseResponse {
  path: string
  parent: string | null
  entries: BrowserEntry[]
}

export interface StateQuery {
  path: string
  log_file?: string
  include_hidden?: boolean
  files_only?: boolean
  dirs_only?: boolean
}

export interface StateResponse {
  valid_path: boolean
  path: string
  log_file: string
  remaining: string[]
  remaining_total: number
  history: string[]
  history_total: number
}

export type PreviewKind =
  | 'text'
  | 'directory'
  | 'binary'
  | 'empty'
  | 'gone'
  | 'unreadable'

export interface PreviewModel {
  kind: PreviewKind
  text: string
  truncated: boolean
  entry_count: number | null
  size: number | null
}

export type PickStatus = 'picked' | 'empty' | 'exhausted' | 'invalid_path'

export interface PickRequest {
  path: string
  log_file?: string | null
  seed?: number | null
  dry_run: boolean
  include_hidden: boolean
  files_only: boolean
  dirs_only: boolean
}

export interface PickResponse {
  status: PickStatus
  log_file: string
  item: string | null
  logged: boolean
  preview: PreviewModel | null
}

export interface OpenResponse {
  opened: string
}

export interface ArchiveResponse {
  log_file: string
  backup: string | null
}

export interface ClearResponse {
  log_file: string
  removed: boolean
}
