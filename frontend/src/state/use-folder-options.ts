import { computed, ref, type ComputedRef, type Ref } from 'vue'

import type { FilterSelection, Mode } from '../view-models.ts'

export interface FolderOptionsBinding {
  path: Ref<string>
  logFile: Ref<string>
  seed: Ref<string>
  dryRun: Ref<boolean>
  includeHidden: Ref<boolean>
  mode: Ref<Mode>
  filters: ComputedRef<FilterSelection>
  entryPath: (item: string) => string
}

/**
 * The single owner of the folder path and the options that shape a pick.
 * Filters stay mutually exclusive here; views only edit the fields.
 */
export function useFolderOptions(): FolderOptionsBinding {
  const path = ref('')
  const logFile = ref('')
  const seed = ref('')
  const dryRun = ref(false)
  const includeHidden = ref(false)
  const mode = ref<Mode>('all')

  const filters = computed<FilterSelection>(() => ({
    include_hidden: includeHidden.value,
    files_only: mode.value === 'files',
    dirs_only: mode.value === 'dirs',
  }))

  function entryPath(item: string): string {
    const base = path.value.replace(/[/\\]+$/, '')
    return `${base}/${item}`
  }

  return {
    path,
    logFile,
    seed,
    dryRun,
    includeHidden,
    mode,
    filters,
    entryPath,
  }
}
