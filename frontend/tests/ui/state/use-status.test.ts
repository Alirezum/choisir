import { describe, expect, it } from 'vitest'

import { ApiError } from '../../../src/api-errors.ts'
import { useStatus } from '../../../src/state/use-status.ts'

describe('useStatus', () => {
  it('starts with the baseline message', () => {
    const { status } = useStatus()

    expect(status.value).toBe('Choose a folder, then press Pick.')
  })

  it('replaces the message through setStatus', () => {
    const { status, setStatus } = useStatus()

    setStatus('Picked only.txt.')

    expect(status.value).toBe('Picked only.txt.')
  })

  it('reports an ApiError through the shared error message path', () => {
    const { status, reportError } = useStatus()

    reportError(new ApiError('That folder does not exist.', 404, 'not_found', null))

    expect(status.value).toBe('That folder does not exist.')
  })

  it('reports arbitrary thrown values exactly as the shared path does', () => {
    const { status, reportError } = useStatus()

    reportError(new Error('transport failed'))

    expect(status.value).toBe('transport failed')

    reportError('plain failure')

    expect(status.value).toBe('plain failure')
  })
})
