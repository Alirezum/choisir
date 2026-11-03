import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { useHistorySelection } from '../../../src/state/use-history-selection.ts'
import type { HistoryEntry } from '../../../src/types.ts'

const entry = (item: string): HistoryEntry => ({
  timestamp: null,
  item,
  display: item,
})

function setup(items: string[] = []) {
  const entries = ref<HistoryEntry[]>(items.map(entry))
  const selection = useHistorySelection({ entries: () => entries.value })
  return { entries, selection }
}

describe('useHistorySelection', () => {
  it('starts with no checked items', () => {
    const { selection } = setup()

    expect(selection.checkedItems.value).toEqual([])
  })

  it('toggles an item on and off in insertion order', () => {
    const { selection } = setup()

    selection.toggle('alpha.txt')
    selection.toggle('beta.txt')
    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])

    selection.toggle('alpha.txt')
    expect(selection.checkedItems.value).toEqual(['beta.txt'])
  })

  it('adds a range as a deduplicated union', () => {
    const { selection } = setup()

    selection.toggle('alpha.txt')
    selection.addRange(['alpha.txt', 'beta.txt', 'gamma.txt'])

    expect(selection.checkedItems.value).toEqual([
      'alpha.txt',
      'beta.txt',
      'gamma.txt',
    ])
  })

  it('selects every unique entry, then clears when all are selected', () => {
    const { selection } = setup(['alpha.txt', 'alpha.txt', 'beta.txt'])

    selection.toggleAll()
    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])

    selection.toggleAll()
    expect(selection.checkedItems.value).toEqual([])
  })

  it('does not select all when only some entries are checked', () => {
    const { selection } = setup(['alpha.txt', 'beta.txt'])

    selection.toggle('alpha.txt')
    selection.toggleAll()

    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'beta.txt'])
  })

  it('clears every checked item', () => {
    const { selection } = setup()

    selection.addRange(['alpha.txt', 'beta.txt'])
    selection.clear()

    expect(selection.checkedItems.value).toEqual([])
  })

  it('removes named items while preserving the rest', () => {
    const { selection } = setup()

    selection.addRange(['alpha.txt', 'beta.txt', 'gamma.txt'])
    selection.remove(['beta.txt'])

    expect(selection.checkedItems.value).toEqual(['alpha.txt', 'gamma.txt'])
  })

  it('prunes checked items that disappeared from the current entries', () => {
    const { entries, selection } = setup(['alpha.txt', 'beta.txt'])

    selection.addRange(['alpha.txt', 'beta.txt'])
    entries.value = [entry('beta.txt'), entry('gamma.txt')]
    selection.pruneMissing()

    expect(selection.checkedItems.value).toEqual(['beta.txt'])
  })
})
