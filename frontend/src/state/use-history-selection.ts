import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

import type { HistoryEntry } from '../types.ts'

export interface HistorySelectionDeps {
  entries: () => HistoryEntry[]
  isBusy?: () => boolean
}

export interface HistorySelectionBinding {
  checkedItems: Ref<string[]>
  anchor: Ref<string | null>
  checkedCount: ComputedRef<number>
  allSelected: ComputedRef<boolean>
  select: (item: string, shift: boolean) => boolean
  toggle: (item: string) => void
  addRange: (items: string[]) => void
  toggleAll: () => void
  clear: () => void
  remove: (items: string[]) => void
  pruneMissing: () => void
}

function uniqueItems(entries: HistoryEntry[]): string[] {
  return [...new Set(entries.map((entry) => entry.item))]
}

/**
 * Owns the checked history rows and the shift-range anchor. Plain clicks
 * toggle and move the anchor; shift clicks extend the range from the anchor
 * without changing it. Returns whether the intent was applied so the
 * composition can decide about previewing.
 */
export function useHistorySelection(
  deps: HistorySelectionDeps,
): HistorySelectionBinding {
  const checkedItems = ref<string[]>([])
  const anchor = ref<string | null>(null)
  const checkedCount = computed(() => checkedItems.value.length)
  const allSelected = computed(() => {
    const entries = deps.entries()
    if (entries.length === 0) return false
    const checked = new Set(checkedItems.value)
    return entries.every((entry) => checked.has(entry.item))
  })

  watch(deps.entries, (entries) => {
    if (anchor.value !== null && !entries.some((entry) => entry.item === anchor.value)) {
      anchor.value = null
    }
  })
  watch(checkedItems, (items) => {
    if (items.length === 0) anchor.value = null
  })

  function toggle(item: string): void {
    checkedItems.value = checkedItems.value.includes(item)
      ? checkedItems.value.filter((name) => name !== item)
      : [...checkedItems.value, item]
  }

  function addRange(items: string[]): void {
    checkedItems.value = [...new Set([...checkedItems.value, ...items])]
  }

  function namesInRange(from: string, to: string): string[] {
    const names = deps.entries().map((entry) => entry.item)
    const start = names.indexOf(from)
    const end = names.indexOf(to)
    if (start === -1 || end === -1) return [to]
    return names.slice(Math.min(start, end), Math.max(start, end) + 1)
  }

  function select(item: string, shift: boolean): boolean {
    if (deps.isBusy?.() === true) return false
    if (shift) {
      if (anchor.value === null) {
        anchor.value = item
        addRange([item])
        return true
      }
      addRange(namesInRange(anchor.value, item))
      return true
    }
    anchor.value = item
    toggle(item)
    return true
  }

  function toggleAll(): void {
    anchor.value = null
    const items = uniqueItems(deps.entries())
    const allSelected =
      items.length > 0 && items.every((item) => checkedItems.value.includes(item))
    checkedItems.value = allSelected ? [] : items
  }

  function clear(): void {
    anchor.value = null
    checkedItems.value = []
  }

  function remove(items: string[]): void {
    const removed = new Set(items)
    checkedItems.value = checkedItems.value.filter(
      (item) => !removed.has(item),
    )
  }

  function pruneMissing(): void {
    const entries = deps.entries()
    const present = new Set(entries.map((entry) => entry.item))
    checkedItems.value = checkedItems.value.filter((item) => present.has(item))
    if (anchor.value !== null && !present.has(anchor.value)) {
      anchor.value = null
    }
  }

  return {
    checkedItems,
    anchor,
    checkedCount,
    allSelected,
    select,
    toggle,
    addRange,
    toggleAll,
    clear,
    remove,
    pruneMissing,
  }
}
