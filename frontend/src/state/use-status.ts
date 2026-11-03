import { ref, type Ref } from 'vue'

import { apiErrorMessage } from '../api-errors.ts'

export const INITIAL_STATUS = 'Choose a folder, then press Pick.'

export interface StatusBinding {
  status: Ref<string>
  setStatus: (message: string) => void
  reportError: (error: unknown) => void
}

/**
 * The single owner of the status line. Failures are converted here only, using
 * the shared client's error message path.
 */
export function useStatus(): StatusBinding {
  const status = ref(INITIAL_STATUS)

  function setStatus(message: string): void {
    status.value = message
  }

  function reportError(error: unknown): void {
    status.value = apiErrorMessage(error)
  }

  return { status, setStatus, reportError }
}
