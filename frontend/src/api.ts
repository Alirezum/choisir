// The single API boundary for the frontend. Screens and components import this
// facade only; see specs/003-frontend-api-client/contracts/
// frontend-api-client.md for the public surface and encoding rules.

import { encodeQuery, type QueryValue } from './api-query.ts'
import { operations, type ApiOperation } from './api-operations.ts'
import { routes } from './api-contract.generated.ts'
import { errorFromResponse, errorFromTransport, parseSuccessJson } from './api-errors.ts'
import type {
  ArchiveResponse,
  BrowseResponse,
  ClearResponse,
  DefaultsResponse,
  FilteredStateRequest,
  FilteredStateResponse,
  OpenResponse,
  PickRequest,
  PickResponse,
  PreviewModel,
  RemoveHistoryItemResponse,
  RemoveHistoryItemsResponse,
  StateQuery,
  StateResponse,
} from './types.ts'

export { ApiError, apiErrorMessage } from './api-errors.ts'

function requestUrl(operation: ApiOperation, params: Record<string, QueryValue>): string {
  return `${routes[operations[operation]].path}${encodeQuery(params)}`
}

function requestMethod(operation: ApiOperation): string {
  return routes[operations[operation]].method
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (cause) {
    throw errorFromTransport(cause)
  }
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  return parseSuccessJson<T>(response)
}

function postJson<T>(operation: ApiOperation, body: unknown): Promise<T> {
  return request<T>(requestUrl(operation, {}), {
    method: requestMethod(operation),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  defaults: () =>
    request<DefaultsResponse>(requestUrl('defaults', {}), {
      method: requestMethod('defaults'),
    }),

  browse: (path: string) =>
    request<BrowseResponse>(requestUrl('browse', { path }), {
      method: requestMethod('browse'),
    }),

  state: (params: StateQuery) =>
    request<StateResponse>(requestUrl('state', { ...params }), {
      method: requestMethod('state'),
    }),

  stateFiltered: (body: FilteredStateRequest) =>
    postJson<FilteredStateResponse>('stateFiltered', body),

  pick: (body: PickRequest) => postJson<PickResponse>('pick', body),

  preview: (path: string) =>
    request<PreviewModel>(requestUrl('preview', { path }), {
      method: requestMethod('preview'),
    }),

  imageUrl: (
    path: string,
    index: number | null = null,
    variant: 'thumb' | 'preview' | null = null,
  ) => requestUrl('imageUrl', { path, index, variant }),

  videoUrl: (path: string) => requestUrl('videoUrl', { path }),

  open: (path: string) => postJson<OpenResponse>('open', { path }),

  archive: (path: string, logFile: string) =>
    request<ArchiveResponse>(requestUrl('archive', { path, log_file: logFile }), {
      method: requestMethod('archive'),
    }),

  clear: (path: string, logFile: string) =>
    request<ClearResponse>(requestUrl('clear', { path, log_file: logFile }), {
      method: requestMethod('clear'),
    }),

  removeHistoryItem: (path: string, logFile: string, item: string) =>
    request<RemoveHistoryItemResponse>(
      requestUrl('removeHistoryItem', { path, item, log_file: logFile }),
      { method: requestMethod('removeHistoryItem') },
    ),

  removeHistoryItems: (path: string, logFile: string, items: string[]) =>
    postJson<RemoveHistoryItemsResponse>('removeHistoryItems', {
      path,
      log_file: logFile === '' ? null : logFile,
      items,
    }),
}
