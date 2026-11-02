// Shared query encoding for the API facade. This is the only module that
// builds query strings; see specs/003-frontend-api-client/contracts/
// frontend-api-client.md section 4 for the value rules.

export type QueryValue = string | number | boolean | undefined | null

export function encodeQuery(params: Record<string, QueryValue>): string {
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
