import { defineComponent, h } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { vi, type Mock } from 'vitest'

import type {
  ArchiveResponse,
  BrowseResponse,
  ClearPathMemoryResponse,
  ClearResponse,
  DefaultsResponse,
  FilteredStateRequest,
  FilteredStateResponse,
  FilterOptions,
  OpenResponse,
  PathMemoryResponse,
  PickRequest,
  PickResponse,
  PreviewModel,
  RemoveHistoryItemResponse,
  RemoveHistoryItemsResponse,
  RemovePathMemoryResponse,
  StateQuery,
  StateResponse,
} from '../../src/types.ts'

export { flushPromises } from '@vue/test-utils'

export interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T | PromiseLike<T>) => void
  reject: (reason?: unknown) => void
}

export function deferred<T = void>(): Deferred<T> {
  let resolve!: Deferred<T>['resolve']
  let reject!: Deferred<T>['reject']
  const promise = new Promise<T>((accept, refuse) => {
    resolve = accept
    reject = refuse
  })
  return { promise, resolve, reject }
}

export interface HostedComposition<T> {
  result: T
  wrapper: VueWrapper
}

/**
 * Mount a disposable host component so composables that register lifecycle
 * hooks (onMounted/onUnmounted) can be exercised in isolation.
 */
export function mountHost<T>(compose: () => T): HostedComposition<T> {
  let result!: T
  const Host = defineComponent({
    setup() {
      result = compose()
      return () => h('div', { 'data-test': 'host' })
    },
  })
  const wrapper = mount(Host)
  return { result, wrapper }
}

export interface ApiMock {
  defaults: Mock<() => Promise<DefaultsResponse>>
  paths: Mock<() => Promise<PathMemoryResponse>>
  clearPaths: Mock<() => Promise<ClearPathMemoryResponse>>
  removePath: Mock<(path: string) => Promise<RemovePathMemoryResponse>>
  browse: Mock<(path: string) => Promise<BrowseResponse>>
  state: Mock<(params: StateQuery) => Promise<StateResponse>>
  stateFiltered: Mock<
    (body: FilteredStateRequest) => Promise<FilteredStateResponse>
  >
  pick: Mock<(body: PickRequest) => Promise<PickResponse>>
  preview: Mock<(path: string) => Promise<PreviewModel>>
  imageUrl: Mock<
    (
      path: string,
      index?: number | null,
      variant?: 'thumb' | 'preview' | null,
    ) => string
  >
  videoUrl: Mock<(path: string) => string>
  open: Mock<(path: string) => Promise<OpenResponse>>
  archive: Mock<(path: string, logFile: string) => Promise<ArchiveResponse>>
  clear: Mock<(path: string, logFile: string) => Promise<ClearResponse>>
  removeHistoryItem: Mock<
    (path: string, logFile: string, item: string) => Promise<RemoveHistoryItemResponse>
  >
  removeHistoryItems: Mock<
    (
      path: string,
      logFile: string,
      items: string[],
    ) => Promise<RemoveHistoryItemsResponse>
  >
}

export function emptyFilterOptions(): FilterOptions {
  return {
    types: [],
    entries: [],
    entries_total: 0,
    entries_truncated: false,
  }
}

/** A filtered state fixture; pass `filter_options` to exercise the panel. */
export function filteredStateResponse(
  overrides: Partial<FilteredStateResponse> = {},
): FilteredStateResponse {
  return {
    valid_path: true,
    path: '/tmp/choosier',
    log_file: '/tmp/choosier/.choosier.jsonl',
    remaining: [],
    remaining_total: 0,
    history: [],
    history_total: 0,
    filter_options: emptyFilterOptions(),
    known_entry_exclusions: [],
    ...overrides,
  }
}

/**
 * Deterministic fakes for the shared API client. Tests usually install these
 * with vi.spyOn(api, 'state').mockImplementation(mock.state), etc.
 */
export function createApiMock(): ApiMock {
  return {
    defaults: vi.fn(),
    paths: vi.fn(),
    clearPaths: vi.fn(),
    removePath: vi.fn(),
    browse: vi.fn(),
    state: vi.fn(),
    stateFiltered: vi.fn(),
    pick: vi.fn(),
    preview: vi.fn(),
    imageUrl: vi.fn(
      (
        path: string,
        index: number | null = null,
        variant: 'thumb' | 'preview' | null = null,
      ) => `/api/image?path=${encodeURIComponent(path)}&index=${index ?? ''}&variant=${variant ?? ''}`,
    ),
    videoUrl: vi.fn(
      (path: string) => `/api/video?path=${encodeURIComponent(path)}`,
    ),
    open: vi.fn(),
    archive: vi.fn(),
    clear: vi.fn(),
    removeHistoryItem: vi.fn(),
    removeHistoryItems: vi.fn(),
  }
}
