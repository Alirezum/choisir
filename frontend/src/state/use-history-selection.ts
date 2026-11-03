import { ref, type Ref } from 'vue'

import type { HistoryEntry } from '../types.ts'

export interface HistorySelectionDeps {
  entries: () => HistoryEntry[]
}

export interface HistorySelectionBinding {
  checkedItems: Ref<string[]>
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
 * Owns the checked history rows only. Anchor and shift-range interaction move
 * here in US2; removal cleanup and confirmation state stay with the actions
 * unit.
 */
export function useHistorySelection(
  deps: HistorySelectionDeps,
): HistorySelectionBinding {
  const checkedItems = ref<string[]>([])

  function toggle(item: string): void {
    checkedItems.value = checkedItems.value.includes(item)
      ? checkedItems.value.filter((name) => name !== item)
      : [...checkedItems.value, item]
  }

  function addRange(items: string[]): void {
    checkedItems.value = [...new Set([...checkedItems.value, ...items])]
  }

  function toggleAll(): void {
    const items = uniqueItems(deps.entries())
    const allSelected =
      items.length > 0 && items.every((item) => checkedItems.value.includes(item))
    checkedItems.value = allSelected ? [] : items
  }

  function clear(): void {
    checkedItems.value = []
  }

  function remove(items: string[]): void {
    const removed = new Set(items)
    checkedItems.value = checkedItems.value.filter(
      (item) => !removed.has(item),
    )
  }

  function pruneMissing(): void {
    const present = new Set(deps.entries().map((entry) => entry.item))
    checkedItems.value = checkedItems.value.filter((item) => present.has(item))
  }

  return {
    checkedItems,
    toggle,
    addRange,
    toggleAll,
    clear,
    remove,
    pruneMissing,
  }
}
