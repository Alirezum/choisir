import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { useHistorySelection } from '../../../src/state/use-history-selection.ts'
import type { HistoryEntry } from '../../../src/types.ts'
import { mountHost } from '../test-helpers.ts'

const entry = (item: string): HistoryEntry => ({
  timestamp: null,
  item,
  display: item,
})

function setup(items: string[] = [], busy = false) {
  const entries = ref<HistoryEntry[]>(items.map(entry))
  const { result, wrapper } = mountHost(() =>
    useHistorySelection({
      entries: () => entries.value,
      isBusy: () => busy,
    }),
  )
  return { entries, selection: result, wrapper }
}

describe('useHistorySelection', () => {
  it('starts with no checked items and no anchor', () => {
    const { selection, wrapper } = setup()

    expect(selection.checkedItems.value).toEqual([])
    expect(selection.anchor.value).toBeNull()
    wrapper.unmount()
  })

  it('toggles an item on and off in insertion order', () => {
    const { selection, wrapper } = setup()
        selection.toggle('alpha.txt')
    selection.toggle('beta.txt')
    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])

    selection.toggle('alpha.txt')
    expect(selection.checkedItems.value).toEqual(['beta.txt'])
    wrapper.unmount()
  })

  it('adds a range as a deduplicated union', () => {
    const { selection, wrapper } = setup()
        selection.toggle('alpha.txt')
    selection.addRange(['alpha.txt', 'beta.txt', 'gamma.txt'])

    expect(selection.checkedItems.value).toEqual([
      'alpha.txt',
      'beta.txt',
      'gamma.txt',
    ])
    wrapper.unmount()
  })

  it('selects every unique entry, then clears when all are selected', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'alpha.txt', 'beta.txt'])
        selection.toggleAll()
    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])

    selection.toggleAll()
    expect(selection.checkedItems.value).toEqual([])
    wrapper.unmount()
  })

  it('does not select all when only some entries are checked', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.toggle('alpha.txt')
    selection.toggleAll()

    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])
    wrapper.unmount()
  })

  it('clears every checked item', () => {
    const { selection, wrapper } = setup()
        selection.addRange(['alpha.txt', 'beta.txt'])
    selection.clear()

    expect(selection.checkedItems.value).toEqual([])
    wrapper.unmount()
  })

  it('removes named items while preserving the rest', () => {
    const { selection, wrapper } = setup()
        selection.addRange(['alpha.txt', 'beta.txt', 'gamma.txt'])
    selection.remove(['beta.txt'])

    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'gamma.txt'])
    wrapper.unmount()
  })

  it('prunes checked items that disappeared from the current entries', () => {
    const { entries, selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.addRange(['alpha.txt', 'beta.txt'])
    entries.value = [entry('beta.txt'), entry('gamma.txt')]
    selection.pruneMissing()

    expect(selection.checkedItems.value).toEqual(['beta.txt'])
    wrapper.unmount()
  })

  it('reports allSelected only when every entry is checked', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])

    expect(selection.allSelected.value).toBe(false)

    selection.addRange(['alpha.txt'])
    expect(selection.allSelected.value).toBe(false)

    selection.addRange(['beta.txt'])
    expect(selection.allSelected.value).toBe(true)

    selection.toggle('alpha.txt')
    expect(selection.allSelected.value).toBe(false)
    wrapper.unmount()
  })

  it('reports the checked count', () => {
    const { selection, wrapper } = setup()

    selection.addRange(['alpha.txt', 'beta.txt'])
    expect(selection.checkedCount.value).toBe(2)

    selection.clear()
    expect(selection.checkedCount.value).toBe(0)
    wrapper.unmount()
  })

  it('a plain select sets the anchor and checks the item', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.select('beta.txt', false)

    expect(selection.anchor.value).toBe('beta.txt')
    expect(selection.checkedItems.value).toEqual(['beta.txt'])
    wrapper.unmount()
  })

  it('a plain select toggles an already checked item off and keeps the anchor', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.select('beta.txt', false)
    selection.select('beta.txt', false)

    expect(selection.anchor.value).toBe('beta.txt')
    expect(selection.checkedItems.value).toEqual([])
    wrapper.unmount()
  })

  it('a shift select with no anchor checks only that item and sets the anchor', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt', 'gamma.txt'])
        selection.select('gamma.txt', true)

    expect(selection.anchor.value).toBe('gamma.txt')
    expect(selection.checkedItems.value).toEqual(['gamma.txt'])
    wrapper.unmount()
  })

  it('a shift select extends the range from the anchor in both directions', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt', 'gamma.txt', 'delta.txt'])
        selection.select('alpha.txt', false)
    selection.select('delta.txt', true)
    expect(selection.checkedItems.value).toEqual([
      'alpha.txt',
      'beta.txt',
      'gamma.txt',
      'delta.txt',
    ])

    selection.clear()
    selection.select('delta.txt', false)
    selection.select('alpha.txt', true)
    expect(selection.checkedItems.value).toEqual([
      'delta.txt',
      'alpha.txt',
      'beta.txt',
      'gamma.txt',
    ])
    wrapper.unmount()
  })

  it('a shift select keeps the anchor so the next shift extends further', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt', 'gamma.txt'])
        selection.select('alpha.txt', false)
    selection.select('beta.txt', true)
    selection.select('gamma.txt', true)

    expect(selection.checkedItems.value).toEqual([
      'alpha.txt',
      'beta.txt',
      'gamma.txt',
    ])
    expect(selection.anchor.value).toBe('alpha.txt')
    wrapper.unmount()
  })

  it('shift select and select all reset the anchor', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.select('alpha.txt', true)
    expect(selection.anchor.value).toBe('alpha.txt')

    selection.toggleAll()
    expect(selection.anchor.value).toBeNull()
    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])

    selection.select('beta.txt', true)
    selection.clear()
    expect(selection.anchor.value).toBeNull()
    wrapper.unmount()
  })

  it('drops the anchor when the entries no longer contain it', () => {
    const { entries, selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.select('alpha.txt', false)
    entries.value = [entry('beta.txt')]
    selection.pruneMissing()

    expect(selection.anchor.value).toBeNull()
    expect(selection.checkedItems.value).toEqual([])
    wrapper.unmount()
  })

  it('ignores selects while busy', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'], true)
        selection.select('alpha.txt', false)
    selection.select('beta.txt', true)

    expect(selection.checkedItems.value).toEqual([])
    expect(selection.anchor.value).toBeNull()
    wrapper.unmount()
  })

  it('keeps the anchor when a removed item is not the anchor', () => {
    const { selection, wrapper } = setup(['alpha.txt', 'beta.txt'])
        selection.select('alpha.txt', false)
    selection.remove(['beta.txt'])

    expect(selection.anchor.value).toBe('alpha.txt')
    wrapper.unmount()
  })
})
