// Tests for the generated route map, the operation map, and the public facade.
// Run with: node --test tests/api-contract.test.mjs

import { readFile } from 'node:fs/promises'
import test from 'node:test'
import assert from 'node:assert/strict'

import { api } from '../src/api.ts'
import { operations } from '../src/api-operations.ts'
import { errorCodes, routes } from '../src/api-contract.generated.ts'

const contract = JSON.parse(
  await readFile(
    new URL(
      '../../specs/001-standardize-api-responses/contracts/api-contract.json',
      import.meta.url,
    ),
    'utf8',
  ),
)

const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })

const originalFetch = globalThis.fetch
const fetchCalls = []

async function withStubbedFetch(fn, respond) {
  const handler = respond ?? (() => Promise.resolve(jsonResponse({ ok: true })))
  fetchCalls.length = 0
  globalThis.fetch = (input, init) => {
    fetchCalls.push({ url: String(input), ...init })
    return handler(input, init)
  }
  try {
    return await fn()
  } finally {
    globalThis.fetch = originalFetch
  }
}

function expectSingleCall() {
  assert.equal(fetchCalls.length, 1)
  const recorded = fetchCalls[0]
  const queryStart = recorded.url.indexOf('?')
  return {
    method: recorded.method ?? 'GET',
    path: queryStart === -1 ? recorded.url : recorded.url.slice(0, queryStart),
    params: new URLSearchParams(queryStart === -1 ? '' : recorded.url.slice(queryStart + 1)),
    body: recorded.body === undefined ? undefined : JSON.parse(recorded.body),
    contentType: recorded.headers === undefined ? undefined : recorded.headers['Content-Type'],
  }
}

const routeFor = (operation) => routes[operations[operation]]

test('the generated surfaces mirror the frozen backend contract', () => {
  const contractRouteKeys = contract.routes.map((route) => `${route.method} ${route.path}`)
  assert.equal(contractRouteKeys.length, 13)
  assert.deepEqual(Object.keys(routes), contractRouteKeys)
  assert.deepEqual([...errorCodes], Object.keys(contract.errorCodes))
})

const operationNames = [
  'defaults',
  'browse',
  'state',
  'stateFiltered',
  'pick',
  'preview',
  'imageUrl',
  'videoUrl',
  'open',
  'archive',
  'clear',
  'removeHistoryItem',
  'removeHistoryItems',
]

test('every generated route maps to exactly one operation and back', () => {
  assert.equal(Object.keys(operations).length, 13)
  assert.deepEqual(Object.keys(operations), operationNames)
  assert.equal(new Set(Object.values(operations)).size, 13)
  assert.deepEqual(Object.values(operations), Object.keys(routes))
})

test('the facade exposes exactly the thirteen operations', () => {
  assert.deepEqual(Object.keys(api), operationNames)
})

test('defaults requests GET /api/defaults', async () => {
  const result = await withStubbedFetch(() => api.defaults())
  assert.deepEqual(result, { ok: true })
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('defaults').method)
  assert.equal(call.path, routeFor('defaults').path)
  assert.equal(call.params.size, 0)
  assert.equal(call.body, undefined)
})

test('browse encodes the path query', async () => {
  await withStubbedFetch(() => api.browse('a b/c?&=ü'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('browse').method)
  assert.equal(call.path, routeFor('browse').path)
  assert.equal(call.params.get('path'), 'a b/c?&=ü')
  assert.equal(call.body, undefined)
})

test('state sends the path, a non-blank log_file, and only true filters', async () => {
  await withStubbedFetch(() =>
    api.state({
      path: '/w',
      log_file: 'a.log',
      include_hidden: true,
      files_only: true,
      dirs_only: false,
    }),
  )
  let call = expectSingleCall()
  assert.equal(call.method, routeFor('state').method)
  assert.equal(call.path, routeFor('state').path)
  assert.equal(call.params.get('path'), '/w')
  assert.equal(call.params.get('log_file'), 'a.log')
  assert.equal(call.params.get('include_hidden'), 'true')
  assert.equal(call.params.get('files_only'), 'true')
  assert.equal(call.params.has('dirs_only'), false)

  await withStubbedFetch(() =>
    api.state({
      path: '/w',
      log_file: '',
      include_hidden: false,
      files_only: true,
      dirs_only: false,
    }),
  )
  call = expectSingleCall()
  assert.equal(call.params.has('log_file'), false)
  assert.equal(call.params.has('include_hidden'), false)
  assert.equal(call.params.get('files_only'), 'true')
})

test('stateFiltered posts the folder flags and exclusions as JSON', async () => {
  const body = {
    path: '/w',
    log_file: '/w/custom.log',
    include_hidden: false,
    files_only: true,
    dirs_only: false,
    excluded_types: ['file:.txt'],
    excluded_entries: ['notes.md'],
  }
  await withStubbedFetch(() => api.stateFiltered(body))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('stateFiltered').method)
  assert.equal(call.method, 'POST')
  assert.equal(call.path, '/api/state')
  assert.equal(call.contentType, 'application/json')
  assert.deepEqual(call.body, body)

  await withStubbedFetch(() =>
    api.stateFiltered({
      path: '/w',
      log_file: null,
      include_hidden: true,
      files_only: false,
      dirs_only: false,
    }),
  )
  const minimal = expectSingleCall()
  assert.deepEqual(minimal.body, {
    path: '/w',
    log_file: null,
    include_hidden: true,
    files_only: false,
    dirs_only: false,
  })
})

test('pick posts its body verbatim as JSON', async () => {
  const body = {
    path: '/w',
    log_file: null,
    seed: null,
    dry_run: false,
    include_hidden: true,
    files_only: false,
    dirs_only: false,
  }
  await withStubbedFetch(() => api.pick(body))
  let call = expectSingleCall()
  assert.equal(call.method, routeFor('pick').method)
  assert.equal(call.path, routeFor('pick').path)
  assert.equal(call.contentType, 'application/json')
  assert.deepEqual(call.body, body)

  await withStubbedFetch(() => api.pick({ ...body, log_file: 'a.log' }))
  call = expectSingleCall()
  assert.equal(call.body.log_file, 'a.log')
})

test('preview encodes the path query', async () => {
  await withStubbedFetch(() => api.preview('a dir/nice file.b64.png'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('preview').method)
  assert.equal(call.path, routeFor('preview').path)
  assert.equal(call.params.get('path'), 'a dir/nice file.b64.png')
})

test('open posts the path as JSON', async () => {
  await withStubbedFetch(() => api.open('/w'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('open').method)
  assert.equal(call.path, routeFor('open').path)
  assert.deepEqual(call.body, { path: '/w' })
})

test('archive posts path and log_file as query parameters', async () => {
  await withStubbedFetch(() => api.archive('/w', 'a.log'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('archive').method)
  assert.equal(call.path, routeFor('archive').path)
  assert.equal(call.params.get('path'), '/w')
  assert.equal(call.params.get('log_file'), 'a.log')
  assert.equal(call.body, undefined)
})

test('clear deletes the log with path and log_file as query parameters', async () => {
  await withStubbedFetch(() => api.clear('/w', 'a.log'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('clear').method)
  assert.equal(call.path, routeFor('clear').path)
  assert.equal(call.params.get('path'), '/w')
  assert.equal(call.params.get('log_file'), 'a.log')
})

test('removeHistoryItem deletes a single entry via query parameters', async () => {
  await withStubbedFetch(() => api.removeHistoryItem('/w', 'a.log', 'item 1'))
  const call = expectSingleCall()
  assert.equal(call.method, routeFor('removeHistoryItem').method)
  assert.equal(call.path, routeFor('removeHistoryItem').path)
  assert.equal(call.params.get('path'), '/w')
  assert.equal(call.params.get('item'), 'item 1')
  assert.equal(call.params.get('log_file'), 'a.log')
})

test('removeHistoryItems posts the selection with null for a blank log_file', async () => {
  await withStubbedFetch(() => api.removeHistoryItems('/w', '', ['item 1', 'item 2']))
  let call = expectSingleCall()
  assert.equal(call.method, routeFor('removeHistoryItems').method)
  assert.equal(call.path, routeFor('removeHistoryItems').path)
  assert.deepEqual(call.body, { path: '/w', log_file: null, items: ['item 1', 'item 2'] })

  await withStubbedFetch(() => api.removeHistoryItems('/w', 'a.log', ['item 3']))
  call = expectSingleCall()
  assert.deepEqual(call.body, { path: '/w', log_file: 'a.log', items: ['item 3'] })
})

test('image and video addresses are built without a fetch call', async () => {
  const parseUrl = (url) => {
    const queryStart = url.indexOf('?')
    return {
      path: queryStart === -1 ? url : url.slice(0, queryStart),
      params: new URLSearchParams(queryStart === -1 ? '' : url.slice(queryStart + 1)),
    }
  }

  await withStubbedFetch(async () => {
    assert.equal(api.imageUrl('/i', 0), '/api/image?path=%2Fi&index=0')
    assert.equal(api.imageUrl('/i'), '/api/image?path=%2Fi')
    assert.equal(api.imageUrl('/i', null, 'thumb'), '/api/image?path=%2Fi&variant=thumb')

    const tricky = parseUrl(api.imageUrl('/i g', 2))
    assert.equal(tricky.path, routeFor('imageUrl').path)
    assert.equal(tricky.params.get('path'), '/i g')
    assert.equal(tricky.params.get('index'), '2')

    const video = parseUrl(api.videoUrl('/v 2'))
    assert.equal(video.path, routeFor('videoUrl').path)
    assert.equal(video.params.get('path'), '/v 2')

    assert.equal(fetchCalls.length, 0)
  })
})

test('a 2xx JSON response is returned unchanged', async () => {
  const payload = { path: '/w', parent: null, entries: [{ name: 'a', is_dir: true }] }
  const result = await withStubbedFetch(() => api.browse('/w'), () =>
    Promise.resolve(jsonResponse(payload)),
  )
  assert.deepEqual(result, payload)
})
