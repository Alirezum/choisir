// Tests for the shared error parser, run with: node --test tests/api-errors.test.mjs

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ApiError,
  apiErrorMessage,
  errorFromResponse,
  errorFromTransport,
  parseSuccessJson,
} from '../src/api-errors.ts'
import { errorCodes } from '../src/api-contract.generated.ts'

const respond = (status, statusText, body, contentType = 'application/json') =>
  new Response(body, { status, statusText, headers: { 'content-type': contentType } })

const jsonRespond = (payload, status, statusText) =>
  respond(status, statusText, JSON.stringify(payload))

test('a standardized envelope becomes one ApiError', async () => {
  const error = await errorFromResponse(
    jsonRespond(
      {
        error: { code: 'not_found', message: 'Not a directory', details: null },
        detail: 'Not a directory',
      },
      404,
      'Not Found',
    ),
  )
  assert.ok(error instanceof ApiError)
  assert.ok(error instanceof Error)
  assert.equal(error.name, 'ApiError')
  assert.deepEqual(
    { status: error.status, code: error.code, message: error.message, details: error.details },
    { status: 404, code: 'not_found', message: 'Not a directory', details: null },
  )
})

test('validation details are preserved unchanged', async () => {
  const details = [{ type: 'value_error', loc: ['pick', 'path'], msg: 'path must not be empty' }]
  const error = await errorFromResponse(
    jsonRespond(
      {
        error: { code: 'validation_error', message: 'Validation failed', details },
        detail: 'Validation failed',
      },
      422,
      'Unprocessable Entity',
    ),
  )
  assert.equal(error.code, 'validation_error')
  assert.deepEqual(error.details, details)
})

test('the envelope takes precedence over a legacy detail field', async () => {
  const error = await errorFromResponse(
    jsonRespond(
      {
        error: { code: 'forbidden', message: 'Forbidden by the server', details: null },
        detail: 'legacy words',
      },
      403,
      'Forbidden',
    ),
  )
  assert.equal(error.message, 'Forbidden by the server')
})

test('every documented code passes through unchanged', async () => {
  assert.equal(errorCodes.length, 9)
  for (const code of errorCodes) {
    const error = await errorFromResponse(
      jsonRespond(
        { error: { code, message: `about ${code}`, details: null }, detail: `about ${code}` },
        422,
        'Unprocessable Entity',
      ),
    )
    assert.equal(error.code, code)
    assert.equal(error.message, `about ${code}`)
  }
})

test('a missing envelope message falls back to the status line', async () => {
  const error = await errorFromResponse(
    jsonRespond({ error: { code: 'forbidden', details: [] } }, 403, 'Forbidden'),
  )
  assert.deepEqual(
    { status: error.status, code: error.code, message: error.message, details: error.details },
    { status: 403, code: 'forbidden', message: '403 Forbidden', details: [] },
  )
})

test('a legacy detail-only body keeps its message without a code', async () => {
  const error = await errorFromResponse(jsonRespond({ detail: 'Legacy text' }, 409, 'Conflict'))
  assert.deepEqual(
    { status: error.status, code: error.code, message: error.message, details: error.details },
    { status: 409, code: null, message: 'Legacy text', details: null },
  )
})

test('an empty body falls back to the status line', async () => {
  const error = await errorFromResponse(respond(503, 'Service Unavailable', ''))
  assert.equal(error.status, 503)
  assert.equal(error.code, null)
  assert.equal(error.message, '503 Service Unavailable')
  assert.equal(error.details, null)
})

test('a non-JSON body falls back to the status line', async () => {
  const error = await errorFromResponse(respond(404, 'Not Found', 'plain text'))
  assert.equal(error.message, '404 Not Found')
  assert.equal(error.code, null)
})

test('a malformed JSON body falls back to the status line', async () => {
  const error = await errorFromResponse(respond(400, 'Bad Request', '{not json'))
  assert.equal(error.message, '400 Bad Request')
  assert.equal(error.code, null)
})

test('an unknown future code is preserved', async () => {
  const error = await errorFromResponse(
    jsonRespond(
      {
        error: {
          code: 'brand_new_code',
          message: 'Some future failure',
          details: { hint: 'extra context' },
        },
        detail: 'legacy words',
      },
      400,
      'Bad Request',
    ),
  )
  assert.deepEqual(
    { status: error.status, code: error.code, message: error.message, details: error.details },
    { status: 400, code: 'brand_new_code', message: 'Some future failure', details: { hint: 'extra context' } },
  )
})

test('parseSuccessJson returns a 2xx JSON body unchanged', async () => {
  const payload = { path: '/w', parent: null, entries: [] }
  const value = await parseSuccessJson(jsonRespond(payload, 200, 'OK'))
  assert.deepEqual(value, payload)
})

test('invalid JSON on a 2xx response never leaks a raw parse exception', async () => {
  await assert.rejects(() => parseSuccessJson(respond(200, 'OK', 'oops{')), (error) => {
    assert.ok(error instanceof ApiError)
    assert.equal(error.status, 200)
    assert.equal(error.code, null)
    assert.equal(error.details, null)
    assert.ok(error.message.includes('Could not parse'))
    assert.ok(!(error instanceof SyntaxError))
    return true
  })
})

test('a transport rejection becomes an ApiError with status 0', () => {
  const error = errorFromTransport(new Error('boom'))
  assert.ok(error instanceof ApiError)
  assert.deepEqual(
    { status: error.status, code: error.code, message: error.message, details: error.details },
    { status: 0, code: null, message: 'boom', details: null },
  )
  assert.equal(errorFromTransport('socket closed').message, 'socket closed')
})

test('apiErrorMessage renders both ApiError and arbitrary thrown values', () => {
  const typed = new ApiError('typed message', 0, null, null)
  assert.equal(apiErrorMessage(typed), 'typed message')
  assert.equal(apiErrorMessage(new Error('plain message')), 'plain message')
  assert.equal(apiErrorMessage('raw string'), 'raw string')
  assert.equal(apiErrorMessage(7), '7')
})
