import { computed, onUnmounted, ref, type ComputedRef, type Ref } from 'vue'

import type { StatusBinding } from './use-status.ts'

/** The fixed cooldown, matching the shared core constant. */
export const SKIP_COOLDOWN_MS = 600_000

export interface SkipRecord {
  name: string
  expiresAt: number
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
  skipping: Ref<boolean>
  skip: (name: string) => Promise<void>
  reconcile: (sent: readonly string[], present: readonly string[]) => void
  reset: () => void
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
  const names = computed(() => records.value.map((record) => record.name))

  function pruneExpired(current: number): boolean {
    const active = records.value.filter((record) => record.expiresAt > current)
    if (active.length === records.value.length) return false
    records.value = active
    return true
  }

  async function skip(name: string): Promise<void> {
    if (skipping.value) return
    const current = now()
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
    if (pruneExpired(now())) {
      void deps.refresh()
    }
  }, TICK_MS)

  onUnmounted(() => {
    window.clearInterval(timer)
  })

  return { records, names, skipping, skip, reconcile, reset }
}
