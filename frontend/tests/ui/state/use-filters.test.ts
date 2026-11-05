import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { useFilters } from '../../../src/state/use-filters.ts'
import type { FilterOptions } from '../../../src/types.ts'

const optionsFixture = (
  overrides: Partial<FilterOptions> = {},
): FilterOptions => ({
  types: [
    { key: 'dir', label: 'Folders', count: 1 },
    { key: 'file:.jpg', label: '.jpg files', count: 2 },
    { key: 'file:.txt', label: '.txt files', count: 1 },
    { key: 'file:', label: 'Files without an extension', count: 1 },
  ],
  entries: [
    { name: 'B.JPG', type_key: 'file:.jpg' },
    { name: 'README', type_key: 'file:' },
    { name: 'a.jpg', type_key: 'file:.jpg' },
    { name: 'notes.txt', type_key: 'file:.txt' },
    { name: 'sub', type_key: 'dir' },
  ],
  entries_total: 5,
  entries_truncated: false,
  ...overrides,
})

const emptyOptions = (): FilterOptions => ({
  types: [],
  entries: [],
  entries_total: 0,
  entries_truncated: false,
})

function setup() {
  const path = ref('/tmp/choosier')
  const logFile = ref('')
  return { path, logFile, filters: useFilters({ path, logFile }) }
}

describe('useFilters', () => {
  it('starts with no exclusions and every option checked', () => {
    const { filters } = setup()
    const options = optionsFixture()
    const panel = filters.panel(options, 3, true)

    expect(filters.exclusions.value).toEqual({
      excluded_types: [],
      excluded_entries: [],
    })
    expect(panel.ready).toBe(true)
    expect(panel.validPath).toBe(true)
    expect(panel.empty).toBe(false)
    expect(panel.checkedTypeKeys).toEqual(
      new Set(['dir', 'file:.jpg', 'file:.txt', 'file:']),
    )
    expect(panel.checkedEntryNames).toEqual(
      new Set(['B.JPG', 'README', 'a.jpg', 'notes.txt', 'sub']),
    )
    expect(panel.active).toBe(false)
    expect(panel.summary).toBe(
      'No filter: all 4 types checked; 3 of 5 entries eligible.',
    )
  })

  it('toggles types without touching entry exclusions', () => {
    const { filters } = setup()
    filters.toggleEntry('notes.txt')
    filters.toggleType('file:.txt')

    const panel = filters.panel(optionsFixture(), 2, true)

    expect(filters.exclusions.value.excluded_types).toEqual(['file:.txt'])
    expect(filters.exclusions.value.excluded_entries).toEqual(['notes.txt'])
    expect(panel.checkedTypeKeys.has('file:.txt')).toBe(false)
    expect(panel.checkedEntryNames.has('notes.txt')).toBe(false)
    expect(panel.active).toBe(true)
    expect(panel.summary).toBe(
      'Filter active: 3 of 4 types checked; 2 of 5 entries eligible.',
    )

    filters.toggleType('file:.txt')
    expect(filters.exclusions.value.excluded_types).toEqual([])
  })

  it('toggles entries without touching type exclusions', () => {
    const { filters } = setup()
    filters.toggleType('dir')
    filters.toggleEntry('B.JPG')

    expect(filters.exclusions.value.excluded_types).toEqual(['dir'])
    expect(filters.exclusions.value.excluded_entries).toEqual(['B.JPG'])

    filters.toggleEntry('B.JPG')
    expect(filters.exclusions.value.excluded_entries).toEqual([])
    expect(filters.exclusions.value.excluded_types).toEqual(['dir'])
  })

  it('keeps exclusions sorted in the request shape', () => {
    const { filters } = setup()
    filters.toggleEntry('sub')
    filters.toggleEntry('B.JPG')
    filters.toggleEntry('a.jpg')
    filters.toggleType('file:.txt')
    filters.toggleType('dir')

    expect(filters.exclusions.value).toEqual({
      excluded_types: ['dir', 'file:.txt'],
      excluded_entries: ['B.JPG', 'a.jpg', 'sub'],
    })
  })

  it('select-all and clear actions use the cached option lists', () => {
    const { filters } = setup()
    const options = optionsFixture()
    filters.reconcile(options, [
      'B.JPG',
      'README',
      'a.jpg',
      'notes.txt',
      'sub',
    ])

    filters.clearTypes()
    expect(filters.exclusions.value.excluded_types).toEqual([
      'dir',
      'file:',
      'file:.jpg',
      'file:.txt',
    ])
    expect(filters.panel(options, 0, true).checkedTypeKeys.size).toBe(0)

    filters.selectAllTypes()
    expect(filters.exclusions.value.excluded_types).toEqual([])

    filters.clearEntries()
    expect(filters.exclusions.value.excluded_entries).toEqual([
      'B.JPG',
      'README',
      'a.jpg',
      'notes.txt',
      'sub',
    ])
    expect(filters.panel(options, 0, true).checkedEntryNames.size).toBe(0)

    filters.selectAllEntries()
    expect(filters.exclusions.value.excluded_entries).toEqual([])
  })

  it('clearFilters clears both kinds in one step', () => {
    const { filters } = setup()
    filters.reconcile(optionsFixture(), ['notes.txt'])
    filters.toggleType('dir')
    filters.toggleEntry('notes.txt')

    filters.clearFilters()

    expect(filters.exclusions.value).toEqual({
      excluded_types: [],
      excluded_entries: [],
    })
  })

  it('reconciles away types that disappeared and entries the server no longer reports', () => {
    const { filters } = setup()
    filters.toggleType('file:.txt')
    filters.toggleType('dir')
    filters.toggleEntry('notes.txt')
    filters.toggleEntry('gone.txt')

    filters.reconcile(
      optionsFixture({
        types: [{ key: 'file:.jpg', label: '.jpg files', count: 2 }],
      }),
      ['notes.txt'],
    )

    expect(filters.exclusions.value).toEqual({
      excluded_types: [],
      excluded_entries: ['notes.txt'],
    })
  })

  it('preserves an exclusion for a name outside the visible entry list', () => {
    const { filters } = setup()
    filters.toggleEntry('outside-the-cap.txt')

    const options = optionsFixture({ entries_truncated: true, entries_total: 5000 })
    filters.reconcile(options, ['outside-the-cap.txt'])

    expect(filters.exclusions.value.excluded_entries).toEqual([
      'outside-the-cap.txt',
    ])
    expect(filters.panel(options, 10, true).entriesTruncated).toBe(true)

    filters.reconcile(options, [])
    expect(filters.exclusions.value.excluded_entries).toEqual([])
  })

  it('treats newly appearing options as checked by default', () => {
    const { filters } = setup()
    filters.toggleType('dir')
    filters.reconcile(optionsFixture(), ['B.JPG'])

    const grown = optionsFixture({
      types: [
        ...optionsFixture().types,
        { key: 'file:.png', label: '.png files', count: 3 },
      ],
    })
    filters.reconcile(grown, ['B.JPG'])

    const panel = filters.panel(grown, 1, true)
    expect(panel.checkedTypeKeys.has('file:.png')).toBe(true)
    expect(filters.exclusions.value.excluded_types).toEqual(['dir'])
  })

  it('resets when the path or log file changes, synchronously', () => {
    const { filters, path, logFile } = setup()
    filters.toggleType('dir')
    filters.toggleEntry('a.jpg')
    filters.reconcile(optionsFixture(), ['a.jpg'])

    path.value = '/tmp/other'

    expect(filters.exclusions.value).toEqual({
      excluded_types: [],
      excluded_entries: [],
    })
    expect(filters.panel(optionsFixture(), 1, true).summary).toBe(
      'No filter: all 4 types checked; 1 of 5 entries eligible.',
    )

    filters.toggleType('file:.txt')
    logFile.value = '/tmp/other/custom.jsonl'
    expect(filters.exclusions.value).toEqual({
      excluded_types: [],
      excluded_entries: [],
    })
  })

  it('increments revision only for actual changes and prunes', () => {
    const { filters } = setup()
    expect(filters.revision.value).toBe(0)

    filters.selectAllTypes()
    filters.selectAllEntries()
    filters.clearFilters()
    expect(filters.revision.value).toBe(0)

    filters.toggleType('dir')
    expect(filters.revision.value).toBe(1)
    filters.toggleType('dir')
    expect(filters.revision.value).toBe(2)

    filters.toggleEntry('a.jpg')
    expect(filters.revision.value).toBe(3)

    filters.reconcile(optionsFixture(), ['a.jpg'])
    expect(filters.revision.value).toBe(3)

    filters.reconcile(optionsFixture(), [])
    expect(filters.revision.value).toBe(4)

    filters.reset()
    expect(filters.revision.value).toBe(5)
  })

  it('reports invalid, not-ready, and empty panel states distinctly', () => {
    const { filters } = setup()

    const notReady = filters.panel(null, 0, false)
    expect(notReady.ready).toBe(false)
    expect(notReady.validPath).toBe(false)
    expect(notReady.empty).toBe(false)
    expect(notReady.summary).toBe('')
    expect(notReady.types).toEqual([])
    expect(notReady.entries).toEqual([])
    expect(notReady.entriesTotal).toBe(0)
    expect(notReady.entriesTruncated).toBe(false)

    const invalid = filters.panel(emptyOptions(), 0, false)
    expect(invalid.ready).toBe(true)
    expect(invalid.validPath).toBe(false)
    expect(invalid.empty).toBe(false)
    expect(invalid.summary).toBe(
      'Choose a valid folder to see filter options.',
    )

    const empty = filters.panel(emptyOptions(), 0, true)
    expect(empty.ready).toBe(true)
    expect(empty.validPath).toBe(true)
    expect(empty.empty).toBe(true)
    expect(empty.summary).toBe('No eligible entries to filter.')
  })

  it('clamps a negative eligible count and pluralizes one type and entry', () => {
    const { filters } = setup()
    const single = optionsFixture({
      types: [{ key: 'dir', label: 'Folders', count: 1 }],
      entries: [{ name: 'sub', type_key: 'dir' }],
      entries_total: 1,
    })

    const panel = filters.panel(single, -3, true)
    expect(panel.eligibleEntries).toBe(0)
    expect(panel.summary).toBe(
      'No filter: all 1 type checked; 0 of 1 entry eligible.',
    )
    expect(panel.entries).toEqual([
      { name: 'sub', typeKey: 'dir', typeLabel: 'Folders' },
    ])
  })

  it('joins each entry row to its type label', () => {
    const { filters } = setup()
    const panel = filters.panel(optionsFixture(), 5, true)

    expect(panel.entries).toEqual([
      { name: 'B.JPG', typeKey: 'file:.jpg', typeLabel: '.jpg files' },
      { name: 'README', typeKey: 'file:', typeLabel: 'Files without an extension' },
      { name: 'a.jpg', typeKey: 'file:.jpg', typeLabel: '.jpg files' },
      { name: 'notes.txt', typeKey: 'file:.txt', typeLabel: '.txt files' },
      { name: 'sub', typeKey: 'dir', typeLabel: 'Folders' },
    ])
  })
})
