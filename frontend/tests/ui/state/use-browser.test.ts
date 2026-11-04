import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useBrowser } from '../../../src/state/use-browser.ts'
import { useStatus } from '../../../src/state/use-status.ts'
import type { BrowseResponse, BrowserEntry } from '../../../src/types.ts'
import { flushPromises, mountHost } from '../test-helpers.ts'

const listing = (
  path = '/tmp/choosier',
  parent: string | null = '/tmp',
  entries: BrowserEntry[] = [],
): BrowseResponse => ({ path, parent, entries })

function setup(pathValue = '/tmp/choosier') {
  const path = ref(pathValue)
  const useFolder = vi.fn()
  const status = useStatus()
  const browse = vi
    .spyOn(api, 'browse')
    .mockResolvedValue(listing(pathValue))
  const { result, wrapper } = mountHost(() =>
    useBrowser({ path, useFolder, status }),
  )
  return { path, useFolder, status, browse, browser: result, wrapper }
}

describe('useBrowser', () => {
  it('loads the current path immediately', async () => {
    const { browse, browser, wrapper } = setup()

    await flushPromises()

    expect(browse).toHaveBeenCalledWith('/tmp/choosier')
    expect(browser.listing.value?.path).toBe('/tmp/choosier')
    expect(browser.error.value).toBe('')
    wrapper.unmount()
  })

  it('does not load a blank path', async () => {
    const { browse, browser, wrapper } = setup('   ')

    await flushPromises()

    expect(browse).not.toHaveBeenCalled()
    expect(browser.listing.value).toBeNull()
    wrapper.unmount()
  })

  it('reloads when the path changes', async () => {
    const { path, browse, browser, wrapper } = setup()

    await flushPromises()
    browse.mockResolvedValueOnce(listing('/tmp/choosier/sub', '/tmp/choosier'))
    path.value = '/tmp/choosier/sub'
    await flushPromises()

    expect(browse).toHaveBeenLastCalledWith('/tmp/choosier/sub')
    expect(browser.listing.value?.path).toBe('/tmp/choosier/sub')
    wrapper.unmount()
  })

  it('stores the shared error message and clears the listing on failure', async () => {
    const { browse, browser, wrapper } = setup()

    await flushPromises()
    browse.mockRejectedValueOnce(new Error('That folder does not exist.'))
    await browser.load('/tmp/missing')

    expect(browser.error.value).toBe('That folder does not exist.')
    expect(browser.listing.value).toBeNull()
    wrapper.unmount()
  })

  it('clears a previous error after a successful load', async () => {
    const { browse, browser, wrapper } = setup()

    await flushPromises()
    browse.mockRejectedValueOnce(new Error('That folder does not exist.'))
    await browser.load('/tmp/missing')
    await browser.load('/tmp/choosier')

    expect(browser.error.value).toBe('')
    expect(browser.listing.value?.path).toBe('/tmp/choosier')
    wrapper.unmount()
  })

  it('navigates into a child directory by joining the stripped base path', async () => {
    const { browse, browser, wrapper } = setup()

    await flushPromises()
    browse.mockResolvedValueOnce(listing('/tmp/choosier/'))
    await browser.load('/tmp/choosier/')
    browse.mockResolvedValueOnce(listing('/tmp/choosier/sub', '/tmp/choosier'))

    browser.navigate({ name: 'sub', is_dir: true })
    await flushPromises()

    expect(browse).toHaveBeenLastCalledWith('/tmp/choosier/sub')
    wrapper.unmount()
  })

  it('ignores files and missing listings when navigating', async () => {
    const { browse, browser, wrapper } = setup('   ')

    await flushPromises()
    browser.navigate({ name: 'notes.txt', is_dir: false })
    browser.navigate({ name: 'sub', is_dir: true })

    expect(browse).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('loads a parent path directly when the target is a string', async () => {
    const { browse, browser, wrapper } = setup()

    await flushPromises()
    browse.mockResolvedValueOnce(listing('/tmp', null))
    browser.navigate('/tmp')
    await flushPromises()

    expect(browse).toHaveBeenLastCalledWith('/tmp')
    expect(browser.listing.value?.path).toBe('/tmp')
    wrapper.unmount()
  })

  it('hands the loaded folder to the use-folder callback', async () => {
    const { useFolder, browser, wrapper } = setup()

    await flushPromises()
    browser.useThisFolder()

    expect(useFolder).toHaveBeenCalledWith('/tmp/choosier')
    wrapper.unmount()
  })

  it('does not use a folder before a listing is loaded', async () => {
    const { useFolder, browser, wrapper } = setup('   ')

    await flushPromises()
    browser.useThisFolder()

    expect(useFolder).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
