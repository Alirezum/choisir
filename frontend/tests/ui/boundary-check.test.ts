import { describe, expect, it } from 'vitest'

import {
  checkBoundaries,
  extractImportSpecifiers,
  findCycles,
  findRawScaffold,
} from '../../scripts/check-ui-boundaries.mjs'

interface Violation {
  rule: string
  file: string
  detail: string
}

function run(
  sources: Record<string, string>,
  tests: string[] = [],
): Violation[] {
  return checkBoundaries({
    sources: new Map(Object.entries(sources)),
    tests: new Set(tests),
  })
}

function rules(violations: Violation[]): string[] {
  return violations.map((violation) => violation.rule)
}

const cleanView = `<script setup lang="ts">
const label = 'Pick'
</script>
<template><p>{{ label }}</p></template>`

describe('boundary check import parsing', () => {
  it('extracts static, type-only, re-exported, and dynamic imports', () => {
    const source = `
      import '@fontsource-variable/archivo'
      import { api } from '../api.ts'
      import type {
        StateResponse,
      } from '../types.ts'
      export { thing } from './thing.ts'
      const lazy = import('./lazy.ts')
    `

    expect(extractImportSpecifiers(source)).toEqual([
      '@fontsource-variable/archivo',
      '../api.ts',
      '../types.ts',
      './thing.ts',
      './lazy.ts',
    ])
  })
})

describe('R-01 view API isolation', () => {
  it('fails a view that imports the API client', () => {
    const violations = run(
      {
        'src/api.ts': 'export const api = {}',
        'src/views/Leaky.vue': `<script setup lang="ts">
import { api } from '../api.ts'
</script>
<template><div>{{ api }}</div></template>`,
      },
      ['tests/ui/views/Leaky.test.ts'],
    )

    expect(rules(violations)).toContain('R-01')
  })

  it('fails a view that fetches an endpoint or reads an error envelope', () => {
    for (const content of [
      `<template><div>{{ fetch('/api/state') }}</div></template>`,
      `<script setup>const message = error.code</script>`,
      `<script setup>const message = error.details</script>`,
      `<script setup>const message = error.detail</script>`,
    ]) {
      const violations = run(
        { 'src/views/Leaky.vue': content },
        ['tests/ui/views/Leaky.test.ts'],
      )
      expect(rules(violations)).toContain('R-01')
    }
  })

  it('passes a presentation-only view', () => {
    const violations = run(
      { 'src/views/Clean.vue': cleanView },
      ['tests/ui/views/Clean.test.ts'],
    )

    expect(violations).toEqual([])
  })
})

describe('R-02 view state isolation', () => {
  it('fails a view that imports a domain state unit', () => {
    const violations = run(
      {
        'src/state/use-browser.ts': 'export function useBrowser() {}',
        'src/views/Leaky.vue': `<script setup>
import { useBrowser } from '../state/use-browser.ts'
</script>`,
      },
      ['tests/ui/state/use-browser.test.ts', 'tests/ui/views/Leaky.test.ts'],
    )

    expect(rules(violations)).toContain('R-02')
  })

  it('allows only the two view-local units in their views', () => {
    const violations = run(
      {
        'src/state/use-preview.ts': 'export function usePreview() {}',
        'src/state/use-image-viewer.ts': 'export function useImageViewer() {}',
        'src/views/PreviewPanel.vue': `<script setup>
import { usePreview } from '../state/use-preview.ts'
</script>`,
        'src/views/ImageViewer.vue': `<script setup>
import { useImageViewer } from '../state/use-image-viewer.ts'
</script>`,
      },
      [
        'tests/ui/state/use-preview.test.ts',
        'tests/ui/state/use-image-viewer.test.ts',
        'tests/ui/views/PreviewPanel.test.ts',
        'tests/ui/views/ImageViewer.test.ts',
      ],
    )

    expect(violations).toEqual([])
  })

  it('fails any other importer of a view-local unit', () => {
    const violations = run(
      {
        'src/state/use-preview.ts': 'export function usePreview() {}',
        'src/state/use-other.ts': `import { usePreview } from './use-preview.ts'`,
      },
      [
        'tests/ui/state/use-preview.test.ts',
        'tests/ui/state/use-other.test.ts',
      ],
    )

    expect(rules(violations)).toContain('R-02')
  })
})

describe('R-03 state isolation', () => {
  it('fails a state unit that imports a view', () => {
    const violations = run(
      {
        'src/views/Leaky.vue': '<template><div /></template>',
        'src/state/use-leaky.ts': `import Leaky from '../views/Leaky.vue'`,
      },
      ['tests/ui/views/Leaky.test.ts', 'tests/ui/state/use-leaky.test.ts'],
    )

    expect(rules(violations)).toContain('R-03')
  })

  it('passes a state unit importing the client and shared types', () => {
    const violations = run(
      {
        'src/api.ts': 'export const api = {}',
        'src/state/use-clean.ts': `import { api } from '../api.ts'`,
      },
      ['tests/ui/state/use-clean.test.ts'],
    )

    expect(violations).toEqual([])
  })
})

describe('R-04 composition-root thinness', () => {
  it('fails API access and orchestration primitives in App.vue', () => {
    for (const content of [
      `<script setup>import { api } from './api.ts'</script>`,
      `<script setup>watch(path, () => {})</script>`,
      `<script setup>const value = computed(() => 1)</script>`,
      `<script setup>onMounted(() => {})</script>`,
      `<script setup>onUnmounted(() => {})</script>`,
      `<script setup>setTimeout(() => {}, 1)</script>`,
      `<script setup>setInterval(() => {}, 1)</script>`,
      `<script setup>api.defaults()</script>`,
      `<script setup>async function start() {}</script>`,
    ]) {
      const sources: Record<string, string> = { 'src/App.vue': content }
      if (content.includes("'./api.ts'")) {
        sources['src/api.ts'] = 'export const api = {}'
      }
      const violations = run(sources)

      expect(rules(violations)).toContain('R-04')
    }
  })

  it('passes a thin App.vue that only wires views and the workspace', () => {
    const violations = run(
      {
        'src/views/Board.vue': '<template><div /></template>',
        'src/state/use-workspace.ts': 'export function useWorkspace() {}',
        'src/App.vue': `<script setup>
import Board from './views/Board.vue'
import { useWorkspace } from './state/use-workspace'
const {} = useWorkspace()
</script>
<template><Board /></template>`,
      },
      [
        'tests/ui/views/Board.test.ts',
        'tests/ui/state/use-workspace.test.ts',
      ],
    )

    expect(violations).toEqual([])
  })
})

describe('R-05 acyclic dependency graph', () => {
  it('fails a relative-import cycle', () => {
    const violations = run({
      'src/a.ts': `import './b.ts'`,
      'src/b.ts': `import './a.ts'`,
    })

    expect(rules(violations)).toContain('R-05')
    expect(findCycles(new Map([
      ['src/a.ts', ['src/b.ts']],
      ['src/b.ts', ['src/a.ts']],
    ]))).toHaveLength(1)
  })

  it('passes an acyclic graph and resolves extensionless imports', () => {
    const violations = run({
      'src/a.ts': `import './b'`,
      'src/b.ts': 'export const b = 1',
    })

    expect(violations).toEqual([])
  })

  it('fails closed on an unresolved relative import', () => {
    const violations = run({ 'src/a.ts': `import './missing.ts'` })

    expect(violations).toContainEqual(
      expect.objectContaining({ rule: 'R-05', file: 'src/a.ts' }),
    )
  })
})

describe('R-06 shared scaffold', () => {
  it('fails raw panel scaffold markup in a view', () => {
    const violations = run(
      {
        'src/views/Raw.vue': `<template><div class="panel"><div class="panel-header">x</div><p class="panel-empty">y</p><div class="panel-actions"></div></div></template>`,
      },
      ['tests/ui/views/Raw.test.ts'],
    )

    expect(rules(violations)).toContain('R-06')
    expect(findRawScaffold('<div class="panel-header">')).toBe('panel-header')
    expect(findRawScaffold('<div class="tab-panel">')).toBeNull()
  })

  it('passes views that use PanelShell and unique classes', () => {
    const violations = run(
      {
        'src/components/PanelShell.vue':
          '<template><div class="panel"><slot /></div></template>',
        'src/views/Clean.vue': `<script setup>
import PanelShell from '../components/PanelShell.vue'
</script>
<template><PanelShell class="browser"><div class="tab-panel" /></PanelShell></template>`,
      },
      [
        'tests/ui/components/PanelShell.test.ts',
        'tests/ui/views/Clean.test.ts',
      ],
    )

    expect(violations).toEqual([])
  })
})

describe('R-07 test-file mapping', () => {
  it('fails a production module without its mapped test', () => {
    const violations = run({ 'src/state/use-missing.ts': 'export {}' })

    expect(violations).toContainEqual(
      expect.objectContaining({
        rule: 'R-07',
        file: 'src/state/use-missing.ts',
        detail: expect.stringContaining(
          'tests/ui/state/use-missing.test.ts',
        ),
      }),
    )
  })

  it('passes when state, view, and component modules have mapped tests', () => {
    const violations = run(
      {
        'src/state/use-thing.ts': 'export {}',
        'src/views/Thing.vue': '<template><div /></template>',
        'src/components/ThingBlock.vue': '<template><div /></template>',
      },
      [
        'tests/ui/state/use-thing.test.ts',
        'tests/ui/views/Thing.test.ts',
        'tests/ui/components/ThingBlock.test.ts',
      ],
    )

    expect(violations).toEqual([])
  })
})
