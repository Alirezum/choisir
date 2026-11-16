import { computed, onUnmounted, ref, type ComputedRef, type Ref } from 'vue'

import type { StatusBinding } from './use-status.ts'

/** The fixed cooldown, matching the shared core constant. */
export const SKIP_COOLDOWN_MS = 600_000

export interface SkipRecord {
  name: string
  expiresAt: number
}

export interface SkippedRow {
  name: string
  returnsIn: string
}

export interface SkipDeps {
  status: Pick<StatusBinding, 'setStatus'>
  refresh: () => Promise<void>
  isRemaining: (name: string) => boolean
  now?: () => number
}

export interface SkipBinding {
  records: Ref<readonly SkipRecord[]>
  names: ComputedRef<string[]>
  skippedRows: ComputedRef<readonly SkippedRow[]>
  skipping: Ref<boolean>
  skip: (name: string) => Promise<void>
  restore: (name: string) => Promise<void>
  restoreAll: () => Promise<void>
  remove: (name: string) => void
  reconcile: (sent: readonly string[], present: readonly string[]) => void
  reset: () => void
}

/** Render a remaining cooldown as `m:ss`, rounding up to the next second. */
export function formatRemaining(ms: number): string {
  const seconds = Math.max(0, Math.ceil(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

const TICK_MS = 1000

/**
 * Owns the browser page's session-only skip records, their monotonic expiry,
 * and the one-second tick. Nothing is written to storage or history.
 */
export function useSkip(deps: SkipDeps): SkipBinding {
  const now = deps.now ?? (() => performance.now())
  const records = ref<readonly SkipRecord[]>([])
  const skipping = ref(false)
  const clock = ref(now())
  const names = computed(() => records.value.map((record) => record.name))
  const skippedRows = computed<readonly SkippedRow[]>(() =>
    [...records.value]
      .sort((left, right) => left.expiresAt - right.expiresAt)
      .map((record) => ({
        name: record.name,
        returnsIn: formatRemaining(record.expiresAt - clock.value),
      })),
  )

  function pruneExpired(current: number): boolean {
    const active = records.value.filter((record) => record.expiresAt > current)
    if (active.length === records.value.length) return false
    records.value = active
    return true
  }

  async function skip(name: string): Promise<void> {
    if (skipping.value) return
    const current = now()
    clock.value = current
    pruneExpired(current)
    if (!deps.isRemaining(name)) {
      deps.status.setStatus(`Could not skip ${name}: it is no longer available.`)
      return
    }
    skipping.value = true
    try {
      records.value = [
        ...records.value.filter((record) => record.name !== name),
        { name, expiresAt: current + SKIP_COOLDOWN_MS },
      ]
      deps.status.setStatus(
        `Skipped ${name}. It returns in ten minutes or when this session ends.`,
      )
      await deps.refresh()
    } finally {
      skipping.value = false
    }
  }

  async function restore(name: string): Promise<void> {
    if (skipping.value) return
    const current = now()
    const exists = records.value.some(
      (record) => record.name === name && record.expiresAt > current,
    )
    if (!exists) {
      pruneExpired(current)
      clock.value = current
      deps.status.setStatus(
        `Could not restore ${name}: it is no longer available.`,
      )
      return
    }
    records.value = records.value.filter((record) => record.name !== name)
    deps.status.setStatus(`Restored ${name}.`)
    skipping.value = true
    try {
      await deps.refresh()
    } finally {
      skipping.value = false
    }
  }

  async function restoreAll(): Promise<void> {
    if (skipping.value) return
    const current = now()
    const active = records.value.filter((record) => record.expiresAt > current)
    if (active.length === 0) {
      pruneExpired(current)
      clock.value = current
      deps.status.setStatus(
        'Could not restore skipped items: nothing is available.',
      )
      return
    }
    records.value = []
    deps.status.setStatus(
      `Restored ${active.length} skipped ${
        active.length === 1 ? 'item' : 'items'
      }.`,
    )
    skipping.value = true
    try {
      await deps.refresh()
    } finally {
      skipping.value = false
    }
  }

  function remove(name: string): void {
    records.value = records.value.filter((record) => record.name !== name)
  }

  function reconcile(sent: readonly string[], present: readonly string[]): void {
    const sentNames = new Set(sent)
    const presentNames = new Set(present)
    records.value = records.value.filter(
      (record) => !sentNames.has(record.name) || presentNames.has(record.name),
    )
  }

  function reset(): void {
    records.value = []
  }

  const timer = window.setInterval(() => {
    const current = now()
    clock.value = current
    if (pruneExpired(current)) {
      void deps.refresh()
    }
  }, TICK_MS)

  onUnmounted(() => {
    window.clearInterval(timer)
  })

  return {
    records,
    names,
    skippedRows,
    skipping,
    skip,
    restore,
    restoreAll,
    remove,
    reconcile,
    reset,
  }
}
