import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PanelShell from '../../../src/components/PanelShell.vue'
import OptionsPanel from '../../../src/views/OptionsPanel.vue'
import type { FilterPanelModel } from '../../../src/view-models.ts'

const filterPanel = (
  overrides: Partial<FilterPanelModel> = {},
): FilterPanelModel => ({
  ready: true,
  validPath: true,
  empty: false,
  eligibleEntries: 3,
  types: [
    { key: 'dir', label: 'Folders', count: 1 },
    { key: 'file:.jpg', label: '.jpg files', count: 2 },
  ],
  entries: [
    { name: 'a.jpg', typeKey: 'file:.jpg', typeLabel: '.jpg files' },
    { name: 'sub', typeKey: 'dir', typeLabel: 'Folders' },
  ],
  checkedTypeKeys: new Set(['dir', 'file:.jpg']),
  checkedEntryNames: new Set(['a.jpg']),
  active: false,
  summary: 'No filter: all 2 types checked; 3 of 3 entries eligible.',
  entriesTotal: 2,
  entriesTruncated: false,
  ...overrides,
})

const notReadyPanel = (): FilterPanelModel =>
  filterPanel({
    ready: false,
    validPath: false,
    empty: false,
    types: [],
    entries: [],
    checkedTypeKeys: new Set(),
    checkedEntryNames: new Set(),
    summary: '',
    entriesTotal: 0,
  })

const mountPanel = (
  panel: FilterPanelModel = notReadyPanel(),
  props: {
    log: string
    seed: string
    dry: boolean
    hidden: boolean
    mode: 'all' | 'files' | 'dirs'
  } = { log: '', seed: '', dry: false, hidden: false, mode: 'all' },
  recent: {
    recentPaths?: string[]
    pathMemoryWarning?: string | null
    pathMemoryNotice?: string
  } = {},
) => mount(OptionsPanel, { props: { ...props, filterPanel: panel, ...recent } })

const button = (wrapper: ReturnType<typeof mountPanel>, label: string) =>
  wrapper.findAll('button').find((item) => item.text() === label)

describe('OptionsPanel', () => {
  it('renders through the shared shell with the header, labels, and placeholders', () => {
    const wrapper = mountPanel()

    expect(wrapper.findComponent(PanelShell).exists()).toBe(true)
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['panel', 'options-panel']),
    )
    expect(wrapper.find('.panel-header').text()).toBe(
      'Changes apply to the next pick.',
    )
    expect(wrapper.find('legend').text()).toBe('Mode')
    expect(
      Array.from(wrapper.findAll('label.field > span')).map((el) => el.text()),
    ).toEqual(['Log file', 'Seed'])
    expect(wrapper.find('input[placeholder]').attributes('placeholder')).toBe(
      'empty = <directory>/.choosier.jsonl',
    )
    expect(wrapper.findAll('input').at(1)?.attributes('placeholder')).toBe(
      'empty = random',
    )
  })

  it('binds the log and seed inputs to their models', async () => {
    const wrapper = mountPanel()
    const [logInput, seedInput] = wrapper.findAll('.field input')

    ;(logInput.element as HTMLInputElement).value = '/tmp/log.jsonl'
    await logInput.trigger('input')
    ;(seedInput.element as HTMLInputElement).value = '42'
    await seedInput.trigger('input')

    expect(wrapper.emitted('update:log')).toEqual([['/tmp/log.jsonl']])
    expect(wrapper.emitted('update:seed')).toEqual([['42']])
  })

  it('binds the dry-run and hidden checkboxes independently of filter rows', async () => {
    const wrapper = mountPanel()
    const checkboxes = wrapper.findAll('.check input[type="checkbox"]')
    expect(checkboxes).toHaveLength(2)

    await checkboxes[0]?.setValue(true)
    await checkboxes[1]?.setValue(true)

    expect(wrapper.emitted('update:dry')).toEqual([[true]])
    expect(wrapper.emitted('update:hidden')).toEqual([[true]])
  })

  it('lists remembered folders with their full paths and emits the chosen one', async () => {
    const paths = ['/home/ana/projects/alpha', '/tmp/choosier/beta']
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: paths,
    })
    const rows = wrapper.findAll('.recent-row')

    expect(rows.map((row) => row.text())).toEqual(paths)
    expect(rows.map((row) => row.attributes('title'))).toEqual(paths)
    expect(rows.map((row) => row.attributes('type'))).toEqual([
      'button',
      'button',
    ])

    await rows[1]?.trigger('click')

    expect(wrapper.emitted('useRecentPath')).toEqual([['/tmp/choosier/beta']])
  })

  it('keeps recent folders keyboard operable through native buttons', () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/home/ana/projects/alpha'],
    })
    const row = wrapper.find('.recent-row')

    expect(row.element.tagName).toBe('BUTTON')
    expect(row.attributes('disabled')).toBeUndefined()
    expect(row.text()).toContain('/home/ana/projects/alpha')
  })

  it('shows the empty state until a folder is remembered', () => {
    const empty = mountPanel(notReadyPanel())
    expect(empty.find('.recent-list').exists()).toBe(false)
    expect(empty.find('.recent-empty').text()).toContain(
      'No remembered folders yet.',
    )

    const populated = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/tmp/choosier'],
    })
    expect(populated.find('.recent-empty').exists()).toBe(false)
    expect(populated.findAll('.recent-row')).toHaveLength(1)
  })

  it('shows the path-memory warning as a status message', () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/tmp/choosier'],
      pathMemoryWarning: 'Skipped 1 unavailable remembered folder.',
    })
    const warning = wrapper.find('.recent-warning')

    expect(warning.attributes('role')).toBe('status')
    expect(warning.text()).toBe('Skipped 1 unavailable remembered folder.')
  })

  it('removes a remembered folder from its row button', async () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/home/ana/projects/alpha', '/tmp/choosier/beta'],
    })
    const removeButtons = wrapper.findAll('.recent-remove')

    expect(removeButtons).toHaveLength(2)
    expect(removeButtons[0]?.attributes('aria-label')).toBe(
      'Remove /home/ana/projects/alpha from remembered folders',
    )
    expect(removeButtons[1]?.attributes('aria-label')).toBe(
      'Remove /tmp/choosier/beta from remembered folders',
    )

    await removeButtons[1]?.trigger('click')

    expect(wrapper.emitted('removeRecentPath')).toEqual([['/tmp/choosier/beta']])
    expect(wrapper.emitted('useRecentPath')).toBeUndefined()
  })

  it('clears every remembered folder with one button', async () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/tmp/choosier'],
    })
    const clear = wrapper.find('.recent-clear')

    expect(clear.text()).toBe('Clear recent folders')
    expect(clear.attributes('disabled')).toBeUndefined()

    await clear.trigger('click')

    expect(wrapper.emitted('clearRecentPaths')).toEqual([[]])
  })

  it('disables clear-all when nothing is remembered', () => {
    const wrapper = mountPanel()

    expect(wrapper.find('.recent-clear').attributes('disabled')).toBeDefined()
  })

  it('keeps row and action controls keyboard operable', () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/home/ana/projects/alpha'],
    })

    for (const selector of ['.recent-row', '.recent-remove', '.recent-clear']) {
      const control = wrapper.find(selector)
      expect(control.element.tagName).toBe('BUTTON')
      expect(control.attributes('type')).toBe('button')
      expect(control.attributes('disabled')).toBeUndefined()
    }
  })

  it('announces action feedback through a polite live region', () => {
    const wrapper = mountPanel(notReadyPanel(), undefined, {
      recentPaths: ['/tmp/choosier'],
      pathMemoryNotice: 'Removed /tmp/choosier from remembered folders.',
    })
    const notice = wrapper.find('.recent-notice')

    expect(notice.attributes('role')).toBe('status')
    expect(notice.attributes('aria-live')).toBe('polite')
    expect(notice.text()).toBe(
      'Removed /tmp/choosier from remembered folders.',
    )
  })

  it('renders the mode radios with all three mutually exclusive choices', () => {
    const wrapper = mountPanel()
    const radios = wrapper.findAll('input[type="radio"]')

    expect(radios).toHaveLength(3)
    expect(radios.map((radio) => radio.attributes('value'))).toEqual([
      'all',
      'files',
      'dirs',
    ])
    expect(radios[0]?.element.checked).toBe(true)
  })

  it('emits a mode change when a radio is selected', async () => {
    const wrapper = mountPanel()
    const radios = wrapper.findAll('input[type="radio"]')

    await radios[1]?.setValue()

    expect(wrapper.emitted('update:mode')).toEqual([['files']])
  })

  it('renders the type checklist with labels, counts, and checked state', () => {
    const wrapper = mountPanel(filterPanel())
    const rows = wrapper.findAll('.filter-group').at(0)?.findAll('.filter-row')

    expect(rows).toHaveLength(2)
    expect(rows?.map((row) => row.find('.filter-name').text())).toEqual([
      'Folders',
      '.jpg files',
    ])
    expect(rows?.map((row) => row.find('.filter-meta').text())).toEqual([
      '1',
      '2',
    ])
    expect(
      rows?.map((row) => (row.find('input').element as HTMLInputElement).checked),
    ).toEqual([true, true])
  })

  it('renders the entry checklist with names, type labels, and checked state', () => {
    const wrapper = mountPanel(filterPanel())
    const rows = wrapper.findAll('.filter-group').at(1)?.findAll('.filter-row')

    expect(rows).toHaveLength(2)
    expect(rows?.map((row) => row.find('.filter-name').text())).toEqual([
      'a.jpg',
      'sub',
    ])
    expect(rows?.map((row) => row.find('.filter-name').attributes('title'))).toEqual(
      ['a.jpg', 'sub'],
    )
    expect(rows?.map((row) => row.find('.filter-meta').text())).toEqual([
      '.jpg files',
      'Folders',
    ])
    expect(
      rows?.map((row) => (row.find('input').element as HTMLInputElement).checked),
    ).toEqual([true, false])
  })

  it('emits the item toggles from the matching checkbox changes', async () => {
    const wrapper = mountPanel(filterPanel())
    const typeRows = wrapper.findAll('.filter-group').at(0)?.findAll('.filter-row')
    const entryRows = wrapper.findAll('.filter-group').at(1)?.findAll('.filter-row')

    await typeRows?.[1].find('input').trigger('change')
    await entryRows?.[1].find('input').trigger('change')

    expect(wrapper.emitted('toggleType')).toEqual([['file:.jpg']])
    expect(wrapper.emitted('toggleEntry')).toEqual([['sub']])
  })

  it('emits each type and entry bulk action and the clear-filters action', async () => {
    const wrapper = mountPanel(filterPanel({ active: true }))

    await button(wrapper, 'Select all types')?.trigger('click')
    await button(wrapper, 'Clear types')?.trigger('click')
    await button(wrapper, 'Select all entries')?.trigger('click')
    await button(wrapper, 'Clear selection')?.trigger('click')
    await button(wrapper, 'Clear filters')?.trigger('click')

    expect(wrapper.emitted('selectAllTypes')).toEqual([[]])
    expect(wrapper.emitted('clearTypes')).toEqual([[]])
    expect(wrapper.emitted('selectAllEntries')).toEqual([[]])
    expect(wrapper.emitted('clearEntries')).toEqual([[]])
    expect(wrapper.emitted('clearFilters')).toEqual([[]])
  })

  it('disables Clear filters when no exclusion is active', () => {
    const active = mountPanel(filterPanel({ active: true }))
    const inactive = mountPanel(filterPanel({ active: false }))

    expect(button(active, 'Clear filters')?.attributes('disabled')).toBeUndefined()
    expect(button(inactive, 'Clear filters')?.attributes('disabled')).toBeDefined()
  })

  it('renders the summary as a polite live region', () => {
    const wrapper = mountPanel(
      filterPanel({ active: true, summary: 'Filter active: 1 of 2 types checked; 1 of 3 entries eligible.' }),
    )
    const summary = wrapper.find('.filter-summary')

    expect(summary.attributes('id')).toBe('filter-summary')
    expect(summary.attributes('aria-live')).toBe('polite')
    expect(summary.text()).toBe(
      'Filter active: 1 of 2 types checked; 1 of 3 entries eligible.',
    )
  })

  it('shows the truncation notice only when entries are capped, without promising hidden entries stay eligible', () => {
    const truncated = mountPanel(
      filterPanel({ entriesTotal: 5000, entriesTruncated: true }),
    )
    const notice = truncated.find('#filter-notice')
    const entryList = truncated.findAll('.filter-list').at(1)

    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('Showing first 2 of 5000 entries.')
    expect(notice.text()).toContain('Entries outside this list are unchanged here')
    expect(notice.text()).not.toContain('still eligible')
    expect(entryList?.attributes('aria-describedby')).toBe(
      'filter-summary filter-notice',
    )

    const complete = mountPanel(filterPanel())
    expect(complete.find('#filter-notice').exists()).toBe(false)
    expect(
      complete.findAll('.filter-list').at(1)?.attributes('aria-describedby'),
    ).toBe('filter-summary')
  })

  it('keeps the actions available while the list is bounded and scrollable', () => {
    const wrapper = mountPanel(
      filterPanel({ entriesTotal: 1200, entriesTruncated: true }),
    )
    const lists = wrapper.findAll('.filter-list')

    expect(lists).toHaveLength(2)
    expect(lists[0]?.attributes('aria-describedby')).toBe('filter-summary')
    expect(button(wrapper, 'Select all entries')).toBeDefined()
    expect(button(wrapper, 'Clear selection')).toBeDefined()
  })

  it('renders invalid, empty, and not-ready states without checklists', () => {
    const invalid = mountPanel(
      filterPanel({
        validPath: false,
        empty: false,
        types: [],
        entries: [],
        summary: 'Choose a valid folder to see filter options.',
      }),
    )
    expect(invalid.find('.filter-summary').text()).toBe(
      'Choose a valid folder to see filter options.',
    )
    expect(invalid.findAll('.filter-list')).toHaveLength(0)
    expect(button(invalid, 'Clear filters')?.attributes('disabled')).toBeDefined()

    const empty = mountPanel(
      filterPanel({
        empty: true,
        types: [],
        entries: [],
        summary: 'No eligible entries to filter.',
      }),
    )
    expect(empty.find('.filter-summary').text()).toBe(
      'No eligible entries to filter.',
    )
    expect(empty.findAll('.filter-list')).toHaveLength(0)

    const notReady = mountPanel(notReadyPanel())
    expect(notReady.find('.filter-summary').text()).toBe(
      'Choose a folder to see filter options.',
    )
    expect(notReady.findAll('.filter-list')).toHaveLength(0)
  })

  it('uses native controls with button types and labelled fieldsets', () => {
    const wrapper = mountPanel(filterPanel())

    expect(wrapper.findAll('fieldset legend').map((el) => el.text())).toEqual([
      'Mode',
      'Types',
      'Entries',
    ])
    expect(
      wrapper.findAll('.filter-actions button').map((el) => el.attributes('type')),
    ).toEqual(['button', 'button', 'button', 'button'])
    expect(
      wrapper.findAll('.filter-row input').map((el) => el.attributes('type')),
    ).toEqual(['checkbox', 'checkbox', 'checkbox', 'checkbox'])
    expect(wrapper.find('.filter-section').attributes('aria-label')).toBe(
      'Filters',
    )
  })
})
