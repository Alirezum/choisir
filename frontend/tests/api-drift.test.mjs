// Contract drift guard: mutating the frozen contract without regenerating
// must fail `--check`; regenerating from the mutated contract recovers.
// Run with: node --test tests/api-drift.test.mjs

import { execFileSync } from 'node:child_process'
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'

const testsDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(testsDir, '..', '..')
const contractPath = path.join(
  repoRoot,
  'specs',
  '001-standardize-api-responses',
  'contracts',
  'api-contract.json',
)
const generatorPath = path.join(repoRoot, 'frontend', 'scripts', 'generate-api-contract.mjs')

function workspace() {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'api-drift-'))
  const contract = path.join(dir, 'contract.json')
  const out = path.join(dir, 'out.generated.ts')
  copyFileSync(contractPath, contract)
  return { dir, contract, out }
}

function run(args) {
  return execFileSync(process.execPath, [generatorPath, ...args], { encoding: 'utf8' })
}

function checkedGeneration({ contract, out }) {
  run(['--contract', contract, '--out', out])
  run(['--check', '--contract', contract, '--out', out])
}

function staleCheckFails({ contract, out }) {
  let failure = null
  try {
    run(['--check', '--contract', contract, '--out', out])
  } catch (error) {
    failure = error
  }
  assert.ok(failure, 'a mutated contract must fail --check')
  assert.equal(failure.status, 1)
  const stderr = typeof failure.stderr === 'string' ? failure.stderr : failure.stderr.toString()
  assert.ok(
    stderr.includes('stale API contract'),
    `expected the stale API contract message, got: ${stderr}`,
  )
}

test('the untouched contract generates and passes --check in a temp directory', () => {
  const space = workspace()
  try {
    checkedGeneration(space)
  } finally {
    rmSync(space.dir, { recursive: true, force: true })
  }
})

const variants = {
  'a removed route'(data) {
    const index = data.routes.findIndex((route) => route.path === '/api/browse')
    data.routes.splice(index, 1)
  },
  'a renamed success field'(data) {
    const defaults = data.routes.find((route) => route.path === '/api/defaults')
    const fields = defaults.success.schema.fields
    const entry = fields.log_file
    delete fields.log_file
    fields.logged_file = entry
  },
  'a removed error code'(data) {
    delete data.errorCodes.forbidden
  },
}

for (const [label, variant] of Object.entries(variants)) {
  test(`a contract with ${label} fails --check and regenerates clean`, () => {
    const space = workspace()
    try {
      checkedGeneration(space)
      const data = JSON.parse(readFileSync(space.contract, 'utf8'))
      variant(data)
      writeFileSync(space.contract, JSON.stringify(data, null, 2))
      staleCheckFails(space)
      run(['--contract', space.contract, '--out', space.out])
      run(['--check', '--contract', space.contract, '--out', space.out])
    } finally {
      rmSync(space.dir, { recursive: true, force: true })
    }
  })
}
