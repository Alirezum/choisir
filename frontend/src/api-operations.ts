// Friendly operation names for the generated API routes. Every value must be a
// route key from frontend/src/api-contract.generated.ts; the type check fails
// when the generated contract changes name, method, or path. The public facade
// in frontend/src/api.ts exposes exactly these operations.

import type { RouteKey } from './api-contract.generated.ts'

export const operations = {
  defaults: 'GET /api/defaults',
  browse: 'GET /api/browse',
  state: 'GET /api/state',
  pick: 'POST /api/pick',
  preview: 'GET /api/preview',
  imageUrl: 'GET /api/image',
  videoUrl: 'GET /api/video',
  open: 'POST /api/open',
  archive: 'POST /api/history/archive',
  clear: 'DELETE /api/history',
  removeHistoryItem: 'DELETE /api/history/item',
  removeHistoryItems: 'POST /api/history/remove',
} as const satisfies Record<string, RouteKey>

export type ApiOperation = keyof typeof operations
