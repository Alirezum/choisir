// Tests for the shared query encoder, run with: node --test tests/api-query.test.mjs

import test from 'node:test'
import assert from 'node:assert/strict'

import { encodeQuery } from '../src/api-query.ts'

test('encodeQuery omits undefined, null, false, and empty strings', () => {
  assert.equal(encodeQuery({ missing: undefined, nothing: null, off: false, blank: '' }), '')
})

test('encodeQuery includes zero as "0"', () => {
  assert.equal(encodeQuery({ index: 0 }), '?index=0')
})

test('encodeQuery includes true as "true"', () => {
  assert.equal(encodeQuery({ files_only: true }), '?files_only=true')
})

test('encodeQuery writes numbers as decimal strings', () => {
  assert.equal(encodeQuery({ whole: -3, decimal: 1.5 }), '?whole=-3&decimal=1.5')
})

test('encodeQuery round-trips tricky strings through URLSearchParams', () => {
  const values = [
    'a b',
    'a/b/c',
    'back\\slash',
    'ünïcodé',
    'punct;:&=+?#',
    'a b/c\\d ü?x=1',
  ]
  for (const value of values) {
    const encoded = encodeQuery({ path: value })
    assert.ok(
      encoded.startsWith('?path='),
      `route selection unchanged for ${JSON.stringify(value)}`,
    )
    assert.equal(new URLSearchParams(encoded.slice(1)).get('path'), value)
  }
})

test('encodeQuery keeps snake_case keys', () => {
  assert.equal(
    encodeQuery({ log_file: 'a.log', files_only: true }),
    '?log_file=a.log&files_only=true',
  )
})

test('encodeQuery returns an empty string when nothing is selected', () => {
  assert.equal(encodeQuery({}), '')
  assert.equal(
    encodeQuery({ missing: undefined, nothing: null, off: false, blank: '' }),
    '',
  )
})
