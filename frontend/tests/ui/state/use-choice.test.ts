import { describe, expect, it } from 'vitest'

import { useChoice } from '../../../src/state/use-choice.ts'
import type { Choice } from '../../../src/view-models.ts'
import type { PreviewModel } from '../../../src/types.ts'

const previewModel = (text: string): PreviewModel => ({
  kind: 'text',
  text,
  truncated: false,
  entry_count: null,
  size: null,
  images: [],
  image_total: 0,
  video: null,
})

const choice = (item: string, preview: PreviewModel | null = null): Choice => ({
  item,
  path: `/tmp/choosier/${item}`,
  preview,
})

describe('useChoice', () => {
  it('starts with no choice and a zero pick serial', () => {
    const { choice: current, pickSerial } = useChoice()

    expect(current.value).toBeNull()
    expect(pickSerial.value).toBe(0)
  })

  it('records a pick and increments the pick serial', () => {
    const { choice: current, pickSerial, setPicked } = useChoice()
    const picked = choice('alpha.txt', previewModel('alpha'))

    setPicked(picked)

    expect(current.value).toEqual(picked)
    expect(pickSerial.value).toBe(1)

    setPicked(choice('beta.txt'))

    expect(current.value?.item).toBe('beta.txt')
    expect(pickSerial.value).toBe(2)
  })

  it('applies the latest preview response only once', () => {
    const { choice: current, beginPreview, applyPreview } = useChoice()
    const target = choice('alpha.txt')

    const request = beginPreview(target)

    expect(current.value).toEqual(target)
    expect(applyPreview(request, previewModel('alpha'))).toBe(true)
    expect(current.value?.preview?.text).toBe('alpha')
    expect(applyPreview(request, previewModel('stale'))).toBe(false)
    expect(current.value?.preview?.text).toBe('alpha')
  })

  it('rejects a preview response superseded by a newer request', () => {
    const { choice: current, beginPreview, applyPreview } = useChoice()

    const first = beginPreview(choice('alpha.txt'))
    const second = beginPreview(choice('beta.txt'))

    expect(second).toBeGreaterThan(first)
    expect(applyPreview(first, previewModel('alpha'))).toBe(false)
    expect(current.value?.item).toBe('beta.txt')
    expect(current.value?.preview).toBeNull()

    expect(applyPreview(second, previewModel('beta'))).toBe(true)
    expect(current.value?.preview?.text).toBe('beta')
  })

  it('invalidates an in-flight preview when a pick lands', () => {
    const { choice: current, pickSerial, beginPreview, applyPreview, setPicked } =
      useChoice()
    const request = beginPreview(choice('alpha.txt'))
    const picked = choice('beta.txt', previewModel('beta'))

    setPicked(picked)

    expect(applyPreview(request, previewModel('stale'))).toBe(false)
    expect(current.value).toEqual(picked)
    expect(pickSerial.value).toBe(1)
  })

  it('invalidates previews and clears the choice without touching the pick serial', () => {
    const { choice: current, pickSerial, beginPreview, applyPreview, setPicked, invalidate } =
      useChoice()
    setPicked(choice('alpha.txt'))
    const request = beginPreview(choice('beta.txt'))

    invalidate()

    expect(current.value).toBeNull()
    expect(pickSerial.value).toBe(1)
    expect(applyPreview(request, previewModel('beta'))).toBe(false)
    expect(current.value).toBeNull()
  })
})
