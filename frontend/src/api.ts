import type {
  ArchiveResponse,
  BrowseResponse,
  ClearResponse,
  DefaultsResponse,
  OpenResponse,
  PickRequest,
  PickResponse,
  PreviewModel,
  RemoveHistoryItemResponse,
  StateQuery,
  StateResponse,
} from './types'

type QueryValue = string | number | boolean | undefined | null

function query(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) {
      continue
    }
    search.set(key, String(value))
  }
  const encoded = search.toString()
  return encoded === '' ? '' : `?${encoded}`
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body: unknown = await response.json()
      if (
        body !== null &&
        typeof body === 'object' &&
        'detail' in body &&
        typeof body.detail === 'string'
      ) {
        detail = body.detail
      }
    } catch {
      // keep the status line as the message
    }
    throw new Error(detail)
  }
  return (await response.json()) as T
}

function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  defaults: () => request<DefaultsResponse>('/api/defaults'),

  browse: (path: string) => request<BrowseResponse>(`/api/browse${query({ path })}`),

  state: (params: StateQuery) => request<StateResponse>(`/api/state${query({ ...params })}`),

  preview: (path: string) => request<PreviewModel>(`/api/preview${query({ path })}`),

  imageUrl: (path: string, index: number | null = null, thumb = false) =>
    `/api/image${query({ path, index, thumb })}`,

  pick: (body: PickRequest) => postJson<PickResponse>('/api/pick', body),

  open: (path: string) => postJson<OpenResponse>('/api/open', { path }),

  archive: (path: string, logFile: string) =>
    request<ArchiveResponse>(`/api/history/archive${query({ path, log_file: logFile })}`, {
      method: 'POST',
    }),

  clear: (path: string, logFile: string) =>
    request<ClearResponse>(`/api/history${query({ path, log_file: logFile })}`, {
      method: 'DELETE',
    }),

  removeHistoryItem: (path: string, logFile: string, item: string) =>
    request<RemoveHistoryItemResponse>(
      `/api/history/item${query({ path, item, log_file: logFile })}`,
      { method: 'DELETE' },
    ),
}
