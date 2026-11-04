import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PanelShell from '../../../src/components/PanelShell.vue'
import type { BrowseResponse, BrowserEntry } from '../../../src/types.ts'
import BrowserPanel from '../../../src/views/BrowserPanel.vue'

const listing = (
  path = '/tmp/choosier',
  parent: string | null = '/tmp',
  entries: BrowserEntry[] = [],
): BrowseResponse => ({ path, parent, entries })

function mountPanel(
  overrides: Partial<{
    path: string
    listing: BrowseResponse | null
    error: string
  }> = {},
) {
  return mount(BrowserPanel, {
    props: {
      path: '/tmp/choosier',
      listing: listing('/tmp/choosier', '/tmp', [
        { name: 'sub', is_dir: true },
        { name: 'notes.txt', is_dir: false },
      ]),
      error: '',
      ...overrides,
    },
  })
}

describe('BrowserPanel', () => {
  it('renders through the shared shell with the listing path in the header', () => {
    const wrapper = mountPanel()

    expect(wrapper.findComponent(PanelShell).exists()).toBe(true)
    const header = wrapper.find('.panel-header')
    expect(header.classes()).toContain('path-line')
    expect(header.text()).toBe('/tmp/choosier')
    expect(header.attributes('title')).toBe('/tmp/choosier')
  })

  it('falls back to the input path before a listing loads', () => {
    const wrapper = mountPanel({ listing: null })

    expect(wrapper.find('.panel-header').text()).toBe('/tmp/choosier')
    expect(wrapper.find('.panel-header').attributes('title')).toBe(
      '/tmp/choosier',
    )
  })

  it('shows the error copy instead of the list', () => {
    const wrapper = mountPanel({ error: 'That folder does not exist.' })

    expect(wrapper.find('.panel-empty.error').text()).toBe(
      'That folder does not exist.',
    )
    expect(wrapper.find('.browser-list').exists()).toBe(false)
  })

  it('renders the parent row, directory rows, and file rows with icons', () => {
    const wrapper = mountPanel()

    const rows = wrapper.findAll('.browser-row')
    expect(rows).toHaveLength(3)
    expect(wrapper.findAll('.browser-list > li')).toHaveLength(3)
    expect(rows[0]?.text()).toBe('Parent folder')
    expect(rows[0]?.element.tagName).toBe('BUTTON')
    expect(rows[1]?.element.tagName).toBe('BUTTON')
    expect(rows[1]?.attributes('title')).toBe('Open sub')
    expect(rows[2]?.element.tagName).toBe('DIV')
    expect(rows[2]?.classes()).toContain('is-file')
    expect(rows[2]?.attributes('title')).toBe('notes.txt')
    expect(wrapper.findAll('.browser-chevron')).toHaveLength(1)
    expect(wrapper.findAll('.row-icon').length).toBeGreaterThanOrEqual(3)
  })

  it('omits the parent row when the listing has no parent', () => {
    const wrapper = mountPanel({ listing: listing('/tmp', null) })

    expect(wrapper.find('.browser-row').exists()).toBe(false)
    expect(wrapper.text()).toContain('This folder is empty.')
  })

  it('shows the empty-folder row for a listing without entries', () => {
    const wrapper = mountPanel({ listing: listing('/tmp/choosier', '/tmp', []) })

    expect(wrapper.find('.browser-empty').text()).toBe('This folder is empty.')
  })

  it('emits navigate with the child entry and the parent path', async () => {
    const wrapper = mountPanel()

    await wrapper.findAll('.browser-row')[0]?.trigger('click')
    await wrapper.findAll('.browser-row')[1]?.trigger('click')

    expect(wrapper.emitted('navigate')).toEqual([
      ['/tmp'],
      [{ name: 'sub', is_dir: true }],
    ])
  })

  it('emits useFolder and disables it without a listing', async () => {
    const wrapper = mountPanel()
    const button = wrapper.find('.panel-actions button')
    expect(button.text()).toBe('Use this folder')

    await button.trigger('click')
    expect(wrapper.emitted('useFolder')).toEqual([[]])

    const empty = mountPanel({ listing: null })
    expect(empty.find('.panel-actions button').attributes('disabled')).toBeDefined()
  })
})
