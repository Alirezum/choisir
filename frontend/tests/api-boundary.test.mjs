// Source-boundary guard: every .vue file must go through the api facade only.
// Run with: node --test tests/api-boundary.test.mjs

import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'

const testsDir = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.resolve(testsDir, '..', 'src')

function collect(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory()) return collect(path.join(dir, entry.name))
    if (entry.name.endsWith('.vue') || entry.name.endsWith('.ts')) {
      return [path.join(dir, entry.name)]
    }
    return []
  })
}

const rel = (file) => path.relative(srcDir, file)
const vueFiles = collect(srcDir).filter((file) => file.endsWith('.vue'))
const tsFiles = collect(srcDir).filter((file) => file.endsWith('.ts'))

test('the scan finds the expected source files', () => {
  assert.ok(vueFiles.length > 0, 'at least one .vue file exists')
  assert.ok(tsFiles.some((file) => rel(file) === 'api.ts'))
})

test('no .vue file touches the network, endpoints, or the envelope', () => {
  const forbidden = [
    /\bfetch\s*\(/,
    /\baxios\b/,
    /\bXMLHttpRequest\b/,
    /\bEventSource\b/,
    /\/api\//,
    /\berror\.code\b/,
    /\berror\.details\b/,
    /\.detail\b/,
  ]
  for (const file of vueFiles) {
    const source = readFileSync(file, 'utf8')
    for (const pattern of forbidden) {
      assert.equal(
        pattern.test(source),
        false,
        `${rel(file)} matched ${pattern}; screens may only call the api facade`,
      )
    }
  }
})

test('fetch( appears exactly once, inside the api facade', () => {
  const matches = tsFiles
    .map((file) => ({
      file: rel(file),
      count: (readFileSync(file, 'utf8').match(/\bfetch\s*\(/g) ?? []).length,
    }))
    .filter((match) => match.count > 0)
  assert.deepEqual(matches, [{ file: 'api.ts', count: 1 }])
})

test('/api/ endpoint literals live only in the generated contract and the operation map', () => {
  const matches = tsFiles
    .filter((file) => /\/api\//.test(readFileSync(file, 'utf8')))
    .map(rel)
    .sort()
  assert.deepEqual(matches, ['api-contract.generated.ts', 'api-operations.ts'])
})

test('envelope field reads live only in the error parser and generated types', () => {
  const envelopePattern = /\berror\.code\b|\berror\.details\b|\.detail\b/
  const allowed = ['api-contract.generated.ts', 'api-errors.ts']
  const matches = tsFiles
    .filter((file) => envelopePattern.test(readFileSync(file, 'utf8')))
    .map(rel)
    .sort()
  assert.ok(matches.length > 0, 'the error parser references envelope fields')
  for (const file of matches) {
    assert.ok(allowed.includes(file), `envelope parsing found in ${file}`)
  }
})
