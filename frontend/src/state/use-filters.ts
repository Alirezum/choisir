import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

import type { FilterExclusions, FilterOptions } from '../types.ts'
import type { FilterEntryRow, FilterPanelModel } from '../view-models.ts'

export interface FilterBinding {
  exclusions: ComputedRef<FilterExclusions>
  revision: Ref<number>
  panel: (
    options: FilterOptions | null,
    eligibleEntries: number,
    validPath: boolean,
  ) => FilterPanelModel
  reconcile: (
    options: FilterOptions,
    knownEntryExclusions: readonly string[],
  ) => void
  reset: () => void
  toggleType: (key: string) => void
  toggleEntry: (name: string) => void
  selectAllTypes: () => void
  clearTypes: () => void
  selectAllEntries: () => void
  clearEntries: () => void
  clearFilters: () => void
}

export interface FiltersDeps {
  path: Ref<string>
  logFile: Ref<string>
}

const EMPTY_OPTIONS: FilterOptions = {
  types: [],
  entries: [],
  entries_total: 0,
  entries_truncated: false,
}

function sorted(values: Iterable<string>): string[] {
  return [...values].sort()
}

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

function sameValues(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index])
}

/**
 * Owns the session-only type and entry exclusions plus the presentation model
 * derived from the latest server filter options. It never calls the API.
 */
export function useFilters(deps: FiltersDeps): FilterBinding {
  const excludedTypes = ref<string[]>([])
  const excludedEntries = ref<string[]>([])
  const revision = ref(0)
  let cachedOptions: FilterOptions | null = null

  const exclusions = computed<FilterExclusions>(() => ({
    excluded_types: [...excludedTypes.value],
    excluded_entries: [...excludedEntries.value],
  }))

  function bump(): void {
    revision.value += 1
  }

  function replaceTypes(next: readonly string[]): void {
    const values = sorted(new Set(next))
    if (sameValues(values, excludedTypes.value)) return
    excludedTypes.value = values
    bump()
  }

  function replaceEntries(next: readonly string[]): void {
    const values = sorted(new Set(next))
    if (sameValues(values, excludedEntries.value)) return
    excludedEntries.value = values
    bump()
  }

  function toggle(type: 'type' | 'entry', value: string): void {
    if (type === 'type') {
      const next = excludedTypes.value.includes(value)
        ? excludedTypes.value.filter((item) => item !== value)
        : [...excludedTypes.value, value]
      replaceTypes(next)
    } else {
      const next = excludedEntries.value.includes(value)
        ? excludedEntries.value.filter((item) => item !== value)
        : [...excludedEntries.value, value]
      replaceEntries(next)
    }
  }

  function reset(): void {
    cachedOptions = null
    excludedTypes.value = []
    excludedEntries.value = []
    bump()
  }

  watch([deps.path, deps.logFile], reset, { flush: 'sync' })

  function reconcile(
    options: FilterOptions,
    knownEntryExclusions: readonly string[],
  ): void {
    cachedOptions = options
    const presentTypes = new Set(options.types.map((item) => item.key))
    const knownEntries = new Set(knownEntryExclusions)
    const nextTypes = excludedTypes.value.filter((key) => presentTypes.has(key))
    const nextEntries = excludedEntries.value.filter((name) => knownEntries.has(name))
    if (!sameValues(nextTypes, excludedTypes.value)) {
      excludedTypes.value = nextTypes
      bump()
    }
    if (!sameValues(nextEntries, excludedEntries.value)) {
      excludedEntries.value = nextEntries
      bump()
    }
  }

  function panel(
    options: FilterOptions | null,
    eligibleEntries: number,
    validPath: boolean,
  ): FilterPanelModel {
    const ready = options !== null
    const available = options ?? EMPTY_OPTIONS
    const pathIsValid = ready && validPath
    const typeLabels = new Map(available.types.map((item) => [item.key, item.label]))
    const excludedTypeSet = new Set(excludedTypes.value)
    const excludedEntrySet = new Set(excludedEntries.value)
    const checkedTypeKeys = new Set(
      available.types
        .map((item) => item.key)
        .filter((key) => !excludedTypeSet.has(key)),
    )
    const checkedEntryNames = new Set(
      available.entries
        .map((item) => item.name)
        .filter((name) => !excludedEntrySet.has(name)),
    )
    const entries: FilterEntryRow[] = available.entries.map((item) => ({
      name: item.name,
      typeKey: item.type_key,
      typeLabel: typeLabels.get(item.type_key) ?? item.type_key,
    }))
    const active = excludedTypes.value.length > 0 || excludedEntries.value.length > 0
    const eligible = Math.max(0, Math.trunc(eligibleEntries))
    const typesCount = available.types.length
    const entriesTotal = available.entries_total

    let summary = ''
    if (ready && !pathIsValid) {
      summary = 'Choose a valid folder to see filter options.'
    } else if (ready && typesCount === 0) {
      summary = 'No eligible entries to filter.'
    } else if (ready) {
      const checked = `${checkedTypeKeys.size} of ${plural(typesCount, 'type', 'types')} checked`
      const eligibleText = `${eligible} of ${plural(entriesTotal, 'entry', 'entries')} eligible`
      summary = active
        ? `Filter active: ${checked}; ${eligibleText}.`
        : `No filter: all ${plural(typesCount, 'type', 'types')} checked; ${eligibleText}.`
    }

    return {
      ready,
      validPath: pathIsValid,
      empty: ready && pathIsValid && typesCount === 0,
      eligibleEntries: eligible,
      types: available.types,
      entries,
      checkedTypeKeys,
      checkedEntryNames,
      active,
      summary,
      entriesTotal,
      entriesTruncated: available.entries_truncated,
    }
  }

  return {
    exclusions,
    revision,
    panel,
    reconcile,
    reset,
    toggleType: (key) => toggle('type', key),
    toggleEntry: (name) => toggle('entry', name),
    selectAllTypes: () => replaceTypes([]),
    clearTypes: () => replaceTypes(cachedOptions?.types.map((item) => item.key) ?? []),
    selectAllEntries: () => replaceEntries([]),
    clearEntries: () =>
      replaceEntries(cachedOptions?.entries.map((item) => item.name) ?? []),
    clearFilters: () => {
      replaceTypes([])
      replaceEntries([])
    },
  }
}
