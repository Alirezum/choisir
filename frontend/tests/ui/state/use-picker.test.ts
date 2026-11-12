import { computed, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { api } from '../../../src/api.ts'
import { useChoice } from '../../../src/state/use-choice.ts'
import { useFolderOptions } from '../../../src/state/use-folder-options.ts'
import { usePicker } from '../../../src/state/use-picker.ts'
import type { PickResponse, PreviewModel } from '../../../src/types.ts'

const preview: PreviewModel = {
  kind: 'text',
  text: 'alpha',
  truncated: false,
  entry_count: null,
  size: 5,
  images: [],
  image_total: 0,
  video: null,
}

const pickResponse = (overrides: Partial<PickResponse> = {}): PickResponse => ({
  status: 'picked',
  log_file: '/tmp/choosier/.choosier.jsonl',
  item: 'alpha.txt',
  logged: true,
  preview,
  path_memory_notice: null,
  ...overrides,
})

function setup() {
  const options = useFolderOptions()
  const choice = useChoice()
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const refresh = vi.fn(async () => {})
  const refreshPathMemory = vi.fn(async () => {})
  const revision = ref(0)
  const excludedTypes = ref<string[]>([])
  const excludedEntries = ref<string[]>([])
  const exclusions = computed(() => ({
    excluded_types: [...excludedTypes.value],
    excluded_entries: [...excludedEntries.value],
  }))
  const pathInput = ref<HTMLInputElement | null>({
    focus: vi.fn(),
  } as unknown as HTMLInputElement)

  const result = usePicker({
    options,
    choice,
    status: { setStatus, reportError },
    refresh,
    refreshPathMemory,
    pathInput,
    filterExclusions: { exclusions, revision },
  })

  return {
    options,
    choice,
    setStatus,
    reportError,
    refresh,
    refreshPathMemory,
    pathInput,
    revision,
    excludedTypes,
    excludedEntries,
    result,
  }
}

describe('usePicker', () => {
  it('rejects a blank path, focuses the input, and stops', async () => {
    const { options, result, setStatus, refresh, pathInput } = setup()
    const pick = vi.spyOn(api, 'pick')
    options.path.value = '   '

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith('Enter a folder path.')
    expect((pathInput.value as unknown as { focus: () => void }).focus).toHaveBeenCalled()
    expect(pick).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('rejects a non-integer seed without a request or refresh', async () => {
    const { options, result, setStatus, refresh } = setup()
    const pick = vi.spyOn(api, 'pick')
    options.path.value = '/tmp/choosier'
    options.seed.value = 'abc'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith('Seed must be a whole number.')
    expect(pick).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('sends nullable log/seed values with the flags and exclusions and records a logged pick', async () => {
    const {
      options,
      choice,
      result,
      setStatus,
      refresh,
      refreshPathMemory,
      excludedTypes,
      excludedEntries,
    } = setup()
    const pick = vi.spyOn(api, 'pick').mockResolvedValue(pickResponse())
    options.path.value = '/tmp/choosier/'
    options.seed.value = ' 42 '
    options.dryRun.value = false
    options.includeHidden.value = true
    options.mode.value = 'files'
    excludedTypes.value = ['dir']
    excludedEntries.value = ['notes.md']

    await result.pick()

    expect(pick).toHaveBeenCalledWith({
      path: '/tmp/choosier/',
      log_file: null,
      seed: 42,
      dry_run: false,
      include_hidden: true,
      files_only: true,
      dirs_only: false,
      excluded_types: ['dir'],
      excluded_entries: ['notes.md'],
    })
    expect(choice.choice.value).toEqual({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview,
    })
    expect(choice.pickSerial.value).toBe(1)
    expect(setStatus).toHaveBeenCalledWith('Picked alpha.txt.')
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(refreshPathMemory).toHaveBeenCalledTimes(1)
  })

  it('uses the dry-run message when the pick was not logged and refreshes the recent list', async () => {
    const { options, result, setStatus, refreshPathMemory } = setup()
    vi.spyOn(api, 'pick').mockResolvedValue(pickResponse({ logged: false }))
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith(
      "Picked alpha.txt. Dry run, so it wasn't logged.",
    )
    expect(refreshPathMemory).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['invalid_path', "That folder doesn't exist."],
    ['empty', 'That folder has nothing to pick.'],
    [
      'exhausted',
      'All items have been picked. Clear or archive history to start over.',
    ],
    [
      'filtered_empty',
      'Filters exclude every entry. Adjust them in Options or clear all filters.',
    ],
    [
      'filtered_exhausted',
      'All entries matching the filters have been picked. Clear filters or reset history to pick more.',
    ],
  ] as const)('reports the %s outcome exactly and refreshes', async (status, message) => {
    const { options, choice, result, setStatus, refresh, refreshPathMemory } =
      setup()
    vi.spyOn(api, 'pick').mockResolvedValue(
      pickResponse({ status, item: null, preview: null }),
    )
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith(message)
    expect(choice.choice.value).toBeNull()
    expect(choice.pickSerial.value).toBe(0)
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(refreshPathMemory).not.toHaveBeenCalled()
  })

  it('appends the path-memory notice to the success status', async () => {
    const { options, result, setStatus } = setup()
    vi.spyOn(api, 'pick').mockResolvedValue(
      pickResponse({ path_memory_notice: 'Could not remember this folder.' }),
    )
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith(
      'Picked alpha.txt. Could not remember this folder.',
    )
  })

  it('leaves the success status unchanged when the notice is null', async () => {
    const { options, result, setStatus } = setup()
    vi.spyOn(api, 'pick').mockResolvedValue(pickResponse())
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith('Picked alpha.txt.')
  })

  it('discards a pick result when the filter revision changed', async () => {
    const { options, choice, result, setStatus, refresh, revision } = setup()
    let resolvePick!: (value: PickResponse) => void
    vi.spyOn(api, 'pick').mockReturnValue(
      new Promise<PickResponse>((resolve) => {
        resolvePick = resolve
      }),
    )
    options.path.value = '/tmp/choosier'

    const pending = result.pick()
    revision.value += 1
    resolvePick(pickResponse())
    await pending

    expect(choice.choice.value).toBeNull()
    expect(setStatus).not.toHaveBeenCalled()
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('discards a pick result when the path changed', async () => {
    const { options, choice, result, setStatus, refresh } = setup()
    let resolvePick!: (value: PickResponse) => void
    vi.spyOn(api, 'pick').mockReturnValue(
      new Promise<PickResponse>((resolve) => {
        resolvePick = resolve
      }),
    )
    options.path.value = '/tmp/choosier'

    const pending = result.pick()
    options.path.value = '/tmp/other'
    resolvePick(pickResponse())
    await pending

    expect(choice.choice.value).toBeNull()
    expect(setStatus).not.toHaveBeenCalled()
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('reports a failed pick through the shared status path and still refreshes', async () => {
    const { options, result, reportError, refresh } = setup()
    const failure = new Error('pick failed')
    vi.spyOn(api, 'pick').mockRejectedValue(failure)
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(reportError).toHaveBeenCalledWith(failure)
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('opens an entry and reports the opened path', async () => {
    const { result, setStatus, reportError } = setup()
    vi.spyOn(api, 'open').mockResolvedValue({ opened: '/tmp/choosier/alpha.txt' })

    await result.openEntry('/tmp/choosier/alpha.txt')

    expect(api.open).toHaveBeenCalledWith('/tmp/choosier/alpha.txt')
    expect(setStatus).toHaveBeenCalledWith('Opened /tmp/choosier/alpha.txt.')
    expect(reportError).not.toHaveBeenCalled()
  })

  it('reports an open failure through the shared status path', async () => {
    const { result, reportError } = setup()
    const failure = new Error('open failed')
    vi.spyOn(api, 'open').mockRejectedValue(failure)

    await result.openEntry('/tmp/choosier/alpha.txt')

    expect(reportError).toHaveBeenCalledWith(failure)
  })

  it('requires a current choice before opening', async () => {
    const { result, setStatus } = setup()
    const open = vi.spyOn(api, 'open')

    await result.openCurrent()

    expect(setStatus).toHaveBeenCalledWith('Pick something first.')
    expect(open).not.toHaveBeenCalled()
  })

  it('opens the current choice path', async () => {
    const { options, choice, result } = setup()
    const open = vi.spyOn(api, 'open').mockResolvedValue({ opened: 'ok' })
    options.path.value = '/tmp/choosier'
    choice.setPicked({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview,
    })

    await result.openCurrent()

    expect(open).toHaveBeenCalledWith('/tmp/choosier/alpha.txt')
  })
})
