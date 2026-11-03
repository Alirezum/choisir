import { describe, expect, it } from 'vitest'

import { useFolderOptions } from '../../../src/state/use-folder-options.ts'

describe('useFolderOptions', () => {
  it('starts with the baseline defaults', () => {
    const options = useFolderOptions()

    expect(options.path.value).toBe('')
    expect(options.logFile.value).toBe('')
    expect(options.seed.value).toBe('')
    expect(options.dryRun.value).toBe(false)
    expect(options.includeHidden.value).toBe(false)
    expect(options.mode.value).toBe('all')
  })

  it('maps hidden and mode state to the API filter flags', () => {
    const options = useFolderOptions()

    expect(options.filters.value).toEqual({
      include_hidden: false,
      files_only: false,
      dirs_only: false,
    })

    options.includeHidden.value = true
    options.mode.value = 'files'

    expect(options.filters.value).toEqual({
      include_hidden: true,
      files_only: true,
      dirs_only: false,
    })

    options.mode.value = 'dirs'

    expect(options.filters.value).toEqual({
      include_hidden: true,
      files_only: false,
      dirs_only: true,
    })

    options.mode.value = 'all'

    expect(options.filters.value).toEqual({
      include_hidden: true,
      files_only: false,
      dirs_only: false,
    })
  })

  it('joins entry paths after removing every trailing separator', () => {
    const { path, entryPath } = useFolderOptions()

    path.value = '/tmp/choosier/'
    expect(entryPath('alpha.txt')).toBe('/tmp/choosier/alpha.txt')

    path.value = '/tmp/choosier///'
    expect(entryPath('alpha.txt')).toBe('/tmp/choosier/alpha.txt')

    path.value = 'C:\\choosier\\\\'
    expect(entryPath('alpha.txt')).toBe('C:\\choosier/alpha.txt')

    path.value = '/tmp/choosier'
    expect(entryPath('alpha.txt')).toBe('/tmp/choosier/alpha.txt')
  })

  it('keeps the baseline slash when the folder path is empty', () => {
    const { entryPath } = useFolderOptions()

    expect(entryPath('alpha.txt')).toBe('/alpha.txt')
  })
})
