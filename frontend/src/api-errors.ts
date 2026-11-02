// One typed error path for every API failure; see specs/003-frontend-api-client/
// contracts/frontend-api-client.md section 3 for the parsing rules. This and the
// generated contract are the only modules allowed to read envelope fields.

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly details: unknown

  constructor(message: string, status: number, code: string | null, details: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function errorFromResponse(response: Response): Promise<ApiError> {
  const status = response.status
  const statusLine = `${status} ${response.statusText}`

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    return new ApiError(statusLine, status, null, null)
  }
  if (body === null || typeof body !== 'object') {
    return new ApiError(statusLine, status, null, null)
  }

  const record = body as { error?: unknown; detail?: unknown }
  const envelope = record.error
  if (envelope !== null && typeof envelope === 'object') {
    const fields = envelope as { code?: unknown; message?: unknown; details?: unknown }
    const code = typeof fields.code === 'string' ? fields.code : null
    if (code !== null || typeof fields.message === 'string') {
      const message =
        typeof fields.message === 'string' && fields.message !== '' ? fields.message : statusLine
      return new ApiError(message, status, code, fields.details ?? null)
    }
  }

  if (typeof record.detail === 'string' && record.detail !== '') {
    return new ApiError(record.detail, status, null, null)
  }

  return new ApiError(statusLine, status, null, null)
}

export function errorFromTransport(cause: unknown): ApiError {
  const message = cause instanceof Error ? cause.message : String(cause)
  return new ApiError(message, 0, null, null)
}

export async function parseSuccessJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(
      `Could not parse the server response as JSON (status ${response.status}).`,
      response.status,
      null,
      null,
    )
  }
}

export function apiErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
