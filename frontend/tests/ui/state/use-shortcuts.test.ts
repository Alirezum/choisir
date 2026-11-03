import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { useShortcuts } from '../../../src/state/use-shortcuts.ts'
import { mountHost } from '../test-helpers.ts'

function setup() {
  const pick = vi.fn()
  const clearing = ref(false)
  const { result, wrapper } = mountHost(() => useShortcuts({ pick, clearing }))
  return { pick, clearing, result, wrapper }
}

function press(key: string, init: KeyboardEventInit = {}) {
  const event = new KeyboardEvent('keydown', {
    key,
    cancelable: true,
    bubbles: true,
    ...init,
  })
  window.dispatchEvent(event)
  return event
}

describe('useShortcuts', () => {
  it('picks on Ctrl+N and prevents the browser default', () => {
    const { pick } = setup()

    const event = press('n', { ctrlKey: true })

    expect(pick).toHaveBeenCalledTimes(1)
    expect(event.defaultPrevented).toBe(true)
  })

  it('accepts uppercase N and extra modifiers', () => {
    const { pick } = setup()

    press('N', { ctrlKey: true, shiftKey: true })

    expect(pick).toHaveBeenCalledTimes(1)
  })

  it('ignores other keys and plain N', () => {
    const { pick } = setup()

    const plain = press('n')
    const other = press('x', { ctrlKey: true })

    expect(pick).not.toHaveBeenCalled()
    expect(plain.defaultPrevented).toBe(false)
    expect(other.defaultPrevented).toBe(false)
  })

  it('blocks the pick while clear is pending, without skipping preventDefault', () => {
    const { pick, clearing } = setup()
    clearing.value = true

    const event = press('n', { ctrlKey: true })

    expect(pick).not.toHaveBeenCalled()
    expect(event.defaultPrevented).toBe(true)
  })

  it('blocks the pick while a dialog or viewer overlay is present', () => {
    const { pick } = setup()

    const dialog = document.createElement('div')
    dialog.className = 'overlay'
    document.body.append(dialog)
    press('n', { ctrlKey: true })
    expect(pick).not.toHaveBeenCalled()
    dialog.remove()

    const viewer = document.createElement('div')
    viewer.className = 'viewer-overlay'
    document.body.append(viewer)
    press('n', { ctrlKey: true })
    expect(pick).not.toHaveBeenCalled()
    viewer.remove()

    press('n', { ctrlKey: true })
    expect(pick).toHaveBeenCalledTimes(1)
  })

  it('removes its window listener on unmount', () => {
    const { pick, wrapper } = setup()

    wrapper.unmount()
    press('n', { ctrlKey: true })

    expect(pick).not.toHaveBeenCalled()
  })
})
