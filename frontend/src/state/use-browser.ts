import { ref, watch, type Ref } from 'vue'

import { api } from '../api.ts'
import type { BrowseResponse, BrowserEntry } from '../types.ts'
import type { StatusBinding } from './use-status.ts'

export interface BrowserDeps {
  path: Ref<string>
  useFolder: (path: string) => void
  status: Pick<StatusBinding, 'describeError'>
}

export interface BrowserBinding {
  listing: Ref<BrowseResponse | null>
  error: Ref<string>
  load: (target: string) => Promise<void>
  navigate: (target: BrowserEntry | string) => void
  useThisFolder: () => void
}

/**
 * Owns the directory listing, its load-on-path-change watcher, parent/child
 * navigation, the inline error message, and the use-folder intent. The header
 * and row presentation stay in the view.
 */
export function useBrowser(deps: BrowserDeps): BrowserBinding {
  const listing = ref<BrowseResponse | null>(null)
  const error = ref('')

  async function load(target: string): Promise<void> {
    if (target.trim() === '') return
    try {
      listing.value = await api.browse(target)
      error.value = ''
    } catch (problem) {
      error.value = deps.status.describeError(problem)
      listing.value = null
    }
  }

  watch(deps.path, (value) => void load(value), { immediate: true })

  function navigate(target: BrowserEntry | string): void {
    if (typeof target === 'string') {
      void load(target)
      return
    }
    if (!target.is_dir || listing.value === null) return
    const base = listing.value.path.replace(/[/\\]+$/, '')
    void load(`${base}/${target.name}`)
  }

  function useThisFolder(): void {
    if (listing.value !== null) deps.useFolder(listing.value.path)
  }

  return { listing, error, load, navigate, useThisFolder }
}
