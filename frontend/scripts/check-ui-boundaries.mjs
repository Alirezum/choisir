#!/usr/bin/env node
import { readdir, readFile } from 'node:fs/promises'
import { basename, dirname, join, posix, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const RULE_NAMES = Object.freeze({
  'R-01': 'view API isolation',
  'R-02': 'view state isolation',
  'R-03': 'state isolation',
  'R-04': 'composition-root thinness',
  'R-05': 'acyclic dependency graph',
  'R-06': 'shared scaffold',
  'R-07': 'test-file mapping',
})

const SRC_PREFIX = 'src/'
const STATE_PREFIX = 'src/state/'
const VIEWS_PREFIX = 'src/views/'
const COMPONENTS_PREFIX = 'src/components/'
const TEST_ROOT = 'tests/ui/'

const API_MODULE_NAMES = new Set([
  'api.ts',
  'api-query.ts',
  'api-operations.ts',
  'api-errors.ts',
  'api-contract.generated.ts',
])

const VIEW_LOCAL_ALLOWLIST = new Map([
  ['src/views/PreviewPanel.vue', 'src/state/use-preview.ts'],
  ['src/views/ImageViewer.vue', 'src/state/use-image-viewer.ts'],
])
const VIEW_LOCAL_UNITS = new Set(VIEW_LOCAL_ALLOWLIST.values())

const SCAFFOLD_TOKENS = new Set([
  'panel',
  'panel-header',
  'panel-empty',
  'panel-actions',
])

const VIEW_API_PATTERNS = [
  ['fetch(', /\bfetch\s*\(/],
  ['XMLHttpRequest', /\bXMLHttpRequest\b/],
  ['EventSource', /\bEventSource\b/],
  ['axios', /\baxios\b/],
  ['/api/', /\/api\//],
  ['error.code', /\berror\.code\b/],
  ['error.details', /\berror\.details\b/],
  ['.detail', /\.detail\b/],
]

const APP_PATTERNS = [
  ['api.', /\bapi\./],
  ['fetch(', /\bfetch\s*\(/],
  ['XMLHttpRequest', /\bXMLHttpRequest\b/],
  ['EventSource', /\bEventSource\b/],
  ['axios', /\baxios\b/],
  ['/api/', /\/api\//],
  ['watch(', /\bwatch\s*\(/],
  ['computed(', /\bcomputed\s*\(/],
  ['onMounted(', /\bonMounted\s*\(/],
  ['onUnmounted(', /\bonUnmounted\s*\(/],
  ['setTimeout', /\bsetTimeout\b/],
  ['setInterval', /\bsetInterval\b/],
  ['apiErrorMessage', /\bapiErrorMessage\b/],
  ['async function', /\basync\s+(?:function\b|[A-Za-z_$][\w$]*\s*\(|\([^)]*?\)\s*=>)/],
]

const STATIC_IMPORT = /(?:^|\n)[ \t]*import\s+(?:type\s+)?(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]/g
const STATIC_EXPORT = /(?:^|\n)[ \t]*export\s+(?:type\s+)?(?:[^'";]+?\s+from\s+)['"]([^'"]+)['"]/g
const DYNAMIC_IMPORT = /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g

export function normalizePath(value) {
  return value.replaceAll('\\', '/').replace(/^\.\//, '')
}

export function stripComments(source) {
  return source
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:\\])\/\/[^\n]*/g, '$1')
}

export function extractImportSpecifiers(source) {
  const cleaned = stripComments(source)
  const specifiers = []

  for (const pattern of [STATIC_IMPORT, STATIC_EXPORT, DYNAMIC_IMPORT]) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(cleaned)) !== null) {
      const specifier = match[1]
      if (!specifiers.includes(specifier)) specifiers.push(specifier)
    }
  }

  return specifiers
}

export function resolveRelativeImport(fromFile, specifier, knownFiles) {
  if (!specifier.startsWith('.')) return null
  const base = posix.normalize(
    posix.join(posix.dirname(fromFile), specifier),
  )
  const candidates = [
    base,
    `${base}.ts`,
    `${base}.vue`,
    `${base}.mjs`,
    `${base}/index.ts`,
    `${base}/index.vue`,
  ]
  for (const candidate of candidates) {
    if (knownFiles.has(candidate)) return candidate
  }
  return null
}

export function extractTemplate(source) {
  const start = source.indexOf('<template')
  if (start === -1) return ''
  const openEnd = source.indexOf('>', start)
  const end = source.lastIndexOf('</template>')
  if (openEnd === -1 || end === -1 || end <= openEnd) return ''
  return source.slice(openEnd + 1, end)
}

export function findRawScaffold(template) {
  const classPattern = /(?:^|[\s<]):?class\s*=\s*(?:"([^"]*)"|'([^']*)')/g
  let match
  while ((match = classPattern.exec(template)) !== null) {
    const value = match[1] ?? match[2] ?? ''
    const tokens = value.match(/[A-Za-z_][\w-]*/g) ?? []
    for (const token of tokens) {
      if (SCAFFOLD_TOKENS.has(token)) return token
    }
  }
  return null
}

export function findCycles(graph) {
  const state = new Map()
  const stack = []
  const cycles = []
  const seen = new Set()

  function visit(node) {
    state.set(node, 1)
    stack.push(node)
    const neighbours = [...(graph.get(node) ?? [])].sort()
    for (const next of neighbours) {
      const status = state.get(next) ?? 0
      if (status === 0) {
        visit(next)
      } else if (status === 1) {
        const start = stack.indexOf(next)
        if (start !== -1) {
          const cycle = [...stack.slice(start), next]
          const key = canonicalCycle(cycle)
          if (!seen.has(key)) {
            seen.add(key)
            cycles.push(cycle)
          }
        }
      }
    }
    stack.pop()
    state.set(node, 2)
  }

  for (const node of [...graph.keys()].sort()) {
    if ((state.get(node) ?? 0) === 0) visit(node)
  }
  return cycles
}

function canonicalCycle(cycle) {
  const nodes = cycle.slice(0, -1)
  const rotations = nodes.map((_, index) =>
    [...nodes.slice(index), ...nodes.slice(0, index)].join(' -> '),
  )
  return rotations.sort()[0] ?? ''
}

function isSourceNode(file) {
  return file.startsWith(SRC_PREFIX) && /\.(ts|vue)$/.test(file)
}

function isView(file) {
  return file.startsWith(VIEWS_PREFIX) && file.endsWith('.vue')
}

function isState(file) {
  return file.startsWith(STATE_PREFIX) && file.endsWith('.ts')
}

function basenameWithout(file, extension) {
  return posix.basename(file, extension)
}

export function checkBoundaries({ sources, tests = new Set() }) {
  const sourceMap = new Map()
  for (const [file, content] of sources) {
    sourceMap.set(normalizePath(file), content)
  }
  const testSet = new Set([...tests].map(normalizePath))
  const knownFiles = new Set(sourceMap.keys())
  const nodes = [...knownFiles].filter(isSourceNode).sort()

  const violations = []
  const seen = new Set()
  function add(rule, file, detail) {
    const key = `${rule}\u0000${file}\u0000${detail}`
    if (seen.has(key)) return
    seen.add(key)
    violations.push({ rule, name: RULE_NAMES[rule], file, detail })
  }

  const fileData = new Map()
  for (const file of nodes) {
    const raw = sourceMap.get(file) ?? ''
    const cleaned = stripComments(raw)
    const imports = extractImportSpecifiers(raw).map((specifier) => {
      if (!specifier.startsWith('.')) {
        return { specifier, target: null, external: true }
      }
      return {
        specifier,
        target: resolveRelativeImport(file, specifier, knownFiles),
        external: false,
      }
    })
    fileData.set(file, { raw, cleaned, imports })
  }

  const graph = new Map(nodes.map((node) => [node, []]))
  for (const [file, data] of fileData) {
    for (const { specifier, target, external } of data.imports) {
      if (external) continue
      if (target === null) {
        add('R-05', file, `unresolved relative import "${specifier}"`)
        continue
      }
      if (isSourceNode(target)) graph.get(file).push(target)
    }
  }

  for (const file of nodes.filter(isView)) {
    const data = fileData.get(file)
    for (const { target } of data.imports) {
      if (target !== null && API_MODULE_NAMES.has(posix.basename(target))) {
        add('R-01', file, `imports API module ${posix.basename(target)}`)
      }
    }
    for (const [label, pattern] of VIEW_API_PATTERNS) {
      if (pattern.test(data.cleaned)) {
        add('R-01', file, `contains ${label}`)
      }
    }
  }

  for (const file of nodes.filter(isView)) {
    const allowed = VIEW_LOCAL_ALLOWLIST.get(file)
    for (const { target } of fileData.get(file).imports) {
      if (target === null || !target.startsWith(STATE_PREFIX)) continue
      if (target !== allowed) {
        add('R-02', file, `imports state unit ${target}`)
      }
    }
  }
  for (const file of nodes) {
    if (isView(file)) continue
    for (const { target } of fileData.get(file).imports) {
      if (target !== null && VIEW_LOCAL_UNITS.has(target)) {
        add('R-02', file, `imports view-local unit ${target}`)
      }
    }
  }

  for (const file of nodes.filter(isState)) {
    for (const { target } of fileData.get(file).imports) {
      if (
        target !== null &&
        (target.startsWith(VIEWS_PREFIX) ||
          target.startsWith(COMPONENTS_PREFIX))
      ) {
        add('R-03', file, `imports presentation module ${target}`)
      }
    }
  }

  if (fileData.has('src/App.vue')) {
    const data = fileData.get('src/App.vue')
    for (const { target } of data.imports) {
      if (target !== null && API_MODULE_NAMES.has(posix.basename(target))) {
        add('R-04', 'src/App.vue', `imports API module ${posix.basename(target)}`)
      }
    }
    for (const [label, pattern] of APP_PATTERNS) {
      if (pattern.test(data.cleaned)) {
        add('R-04', 'src/App.vue', `contains ${label}`)
      }
    }
  }

  for (const cycle of findCycles(graph)) {
    add('R-05', cycle[0], `relative-import cycle: ${cycle.join(' -> ')}`)
  }

  for (const file of nodes.filter(isView)) {
    const token = findRawScaffold(extractTemplate(fileData.get(file).raw))
    if (token !== null) {
      add('R-06', file, `raw scaffold class "${token}"`)
    }
  }

  for (const file of nodes) {
    let expected = null
    if (file.startsWith(STATE_PREFIX) && file.endsWith('.ts')) {
      expected = `${TEST_ROOT}state/${basenameWithout(file, '.ts')}.test.ts`
    } else if (file.startsWith(VIEWS_PREFIX) && file.endsWith('.vue')) {
      expected = `${TEST_ROOT}views/${basenameWithout(file, '.vue')}.test.ts`
    } else if (
      file.startsWith(COMPONENTS_PREFIX) &&
      file.endsWith('.vue')
    ) {
      expected = `${TEST_ROOT}components/${basenameWithout(file, '.vue')}.test.ts`
    }
    if (expected !== null && !testSet.has(expected)) {
      add('R-07', file, `missing test file ${expected}`)
    }
  }

  violations.sort(
    (left, right) =>
      left.rule.localeCompare(right.rule) ||
      left.file.localeCompare(right.file) ||
      left.detail.localeCompare(right.detail),
  )
  return violations
}

async function collectFiles(directory, root) {
  const files = new Map()
  const entries = await readdir(directory, { withFileTypes: true })
  entries.sort((left, right) => left.name.localeCompare(right.name))

  for (const entry of entries) {
    const full = join(directory, entry.name)
    if (entry.isDirectory()) {
      const nested = await collectFiles(full, root)
      for (const [path, content] of nested) files.set(path, content)
      continue
    }
    if (!entry.isFile()) continue
    const relativePath = normalizePath(relative(root, full))
    try {
      files.set(relativePath, await readFile(full, 'utf8'))
    } catch (error) {
      throw new Error(
        `cannot read ${relativePath}: ${error instanceof Error ? error.message : String(error)}`,
      )
    }
  }

  return files
}

async function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
  const sources = await collectFiles(join(root, 'src'), root)
  const testFiles = await collectFiles(join(root, 'tests', 'ui'), root)
  const violations = checkBoundaries({
    sources,
    tests: new Set(testFiles.keys()),
  })

  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(
        `${violation.rule} ${violation.name}: ${violation.file} — ${violation.detail}`,
      )
    }
    console.error(`\n${violations.length} UI boundary violation(s).`)
    process.exitCode = 1
    return
  }

  console.log(
    `UI boundaries clean: ${sources.size} source files, ${testFiles.size} test files.`,
  )
}

const invokedDirectly =
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  main().catch((error) => {
    console.error(
      `check-ui-boundaries: ${error instanceof Error ? error.message : String(error)}`,
    )
    process.exitCode = 1
  })
}
