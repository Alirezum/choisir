import { ref } from 'vue'
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
  ...overrides,
})

function setup() {
  const options = useFolderOptions()
  const choice = useChoice()
  const setStatus = vi.fn()
  const reportError = vi.fn()
  const refresh = vi.fn(async () => {})
  const pathInput = ref<HTMLInputElement | null>({
    focus: vi.fn(),
  } as unknown as HTMLInputElement)

  const result = usePicker({
    options,
    choice,
    status: { setStatus, reportError },
    refresh,
    pathInput,
  })

  return {
    options,
    choice,
    setStatus,
    reportError,
    refresh,
    pathInput,
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

  it('sends nullable log/seed values with the filters and records a logged pick', async () => {
    const { options, choice, result, setStatus, refresh } = setup()
    const pick = vi.spyOn(api, 'pick').mockResolvedValue(pickResponse())
    options.path.value = '/tmp/choosier/'
    options.seed.value = ' 42 '
    options.dryRun.value = false
    options.includeHidden.value = true
    options.mode.value = 'files'

    await result.pick()

    expect(pick).toHaveBeenCalledWith({
      path: '/tmp/choosier/',
      log_file: null,
      seed: 42,
      dry_run: false,
      include_hidden: true,
      files_only: true,
      dirs_only: false,
    })
    expect(choice.choice.value).toEqual({
      item: 'alpha.txt',
      path: '/tmp/choosier/alpha.txt',
      preview,
    })
    expect(choice.pickSerial.value).toBe(1)
    expect(setStatus).toHaveBeenCalledWith('Picked alpha.txt.')
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('uses the dry-run message when the pick was not logged', async () => {
    const { options, result, setStatus } = setup()
    vi.spyOn(api, 'pick').mockResolvedValue(pickResponse({ logged: false }))
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith(
      "Picked alpha.txt. Dry run, so it wasn't logged.",
    )
  })

  it.each([
    ['invalid_path', "That folder doesn't exist."],
    ['empty', 'That folder has nothing to pick.'],
    [
      'exhausted',
      'All items have been picked. Clear or archive history to start over.',
    ],
  ] as const)('reports the %s outcome exactly and refreshes', async (status, message) => {
    const { options, choice, result, setStatus, refresh } = setup()
    vi.spyOn(api, 'pick').mockResolvedValue(
      pickResponse({ status, item: null, preview: null }),
    )
    options.path.value = '/tmp/choosier'

    await result.pick()

    expect(setStatus).toHaveBeenCalledWith(message)
    expect(choice.choice.value).toBeNull()
    expect(choice.pickSerial.value).toBe(0)
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
