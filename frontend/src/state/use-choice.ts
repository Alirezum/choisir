import { ref, type Ref } from 'vue'

import type { Choice } from '../view-models.ts'
import type { PreviewModel } from '../types.ts'

export interface ChoiceBinding {
  choice: Ref<Choice | null>
  pickSerial: Ref<number>
  setPicked: (picked: Choice) => void
  beginPreview: (target: Choice) => number
  applyPreview: (request: number, preview: PreviewModel) => boolean
  isCurrent: (request: number) => boolean
  invalidate: () => void
}

/**
 * Owns the current choice and the serials that keep late preview responses from
 * overwriting a newer pick or preview. Actions never touch status text.
 */
export function useChoice(): ChoiceBinding {
  const choice = ref<Choice | null>(null)
  const pickSerial = ref(0)
  let previewSerial = 0

  function setPicked(picked: Choice): void {
    previewSerial += 1
    choice.value = picked
    pickSerial.value += 1
  }

  function beginPreview(target: Choice): number {
    previewSerial += 1
    choice.value = target
    return previewSerial
  }

  function applyPreview(request: number, preview: PreviewModel): boolean {
    if (request !== previewSerial) return false
    if (choice.value === null) return false
    choice.value = { ...choice.value, preview }
    // A response is applied once; a duplicate arriving later is stale.
    previewSerial += 1
    return true
  }

  function isCurrent(request: number): boolean {
    return request === previewSerial
  }

  function invalidate(): void {
    previewSerial += 1
    choice.value = null
  }

  return {
    choice,
    pickSerial,
    setPicked,
    beginPreview,
    applyPreview,
    isCurrent,
    invalidate,
  }
}
