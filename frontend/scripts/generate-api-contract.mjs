#!/usr/bin/env node
// Generate the frontend API contract surface from the authoritative JSON
// contract. Run `npm run generate:api` after an approved contract change.

import { readFileSync, renameSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url))
const DEFAULT_CONTRACT = resolve(
  REPO_ROOT,
  'specs/001-standardize-api-responses/contracts/api-contract.json',
)
const DEFAULT_OUTPUT = resolve(REPO_ROOT, 'frontend/src/api-contract.generated.ts')

const METHODS = new Set(['GET', 'POST', 'DELETE'])

const RESPONSE_TYPE_NAMES = {
  'GET /api/defaults': 'DefaultsResponse',
  'GET /api/browse': 'BrowseResponse',
  'GET /api/state': 'StateResponse',
  'POST /api/state': 'FilteredStateResponse',
  'POST /api/pick': 'PickResponse',
  'POST /api/open': 'OpenResponse',
  'POST /api/history/archive': 'ArchiveResponse',
  'DELETE /api/history': 'ClearResponse',
  'DELETE /api/history/item': 'RemoveHistoryItemResponse',
  'POST /api/history/remove': 'RemoveHistoryItemsResponse',
}

function usage() {
  return [
    'Usage: node scripts/generate-api-contract.mjs [options]',
    '',
    'Options:',
    '  --check             verify the checked-in module matches the contract',
    '  --contract <path>   authoritative contract JSON (default: specs/...)',
    '  --out <path>        generated TypeScript module (default: frontend/src/...)',
    '  --help              show this message',
  ].join('\n')
}

function parseArgs(argv) {
  const options = {
    check: false,
    help: false,
    contract: DEFAULT_CONTRACT,
    out: DEFAULT_OUTPUT,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--check') {
      options.check = true
    } else if (arg === '--help' || arg === '-h') {
      options.help = true
    } else if (arg === '--contract' || arg === '--out') {
      const value = argv[index + 1]
      if (value === undefined || value.startsWith('--')) {
        throw new Error(`${arg} requires a path`)
      }
      options[arg === '--contract' ? 'contract' : 'out'] = isAbsolute(value)
        ? value
        : resolve(process.cwd(), value)
      index += 1
    } else {
      throw new Error(`unknown option: ${arg}`)
    }
  }

  return options
}

function loadContract(contractPath) {
  let data
  try {
    data = JSON.parse(readFileSync(contractPath, 'utf8'))
  } catch (error) {
    throw new Error(`cannot read contract ${contractPath}: ${error.message}`)
  }

  if (data === null || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('contract must be a JSON object')
  }
  if (data.version !== 1) {
    throw new Error(`unsupported contract version: ${String(data.version)}`)
  }
  if (data.apiPrefix !== '/api') {
    throw new Error(`unsupported API prefix: ${String(data.apiPrefix)}`)
  }
  if (!Array.isArray(data.routes) || data.routes.length === 0) {
    throw new Error('contract routes must be a non-empty array')
  }
  if (
    data.errorCodes === null ||
    typeof data.errorCodes !== 'object' ||
    Array.isArray(data.errorCodes) ||
    Object.keys(data.errorCodes).length === 0
  ) {
    throw new Error('contract errorCodes must be a non-empty object')
  }
  if (
    data.schemas === null ||
    typeof data.schemas !== 'object' ||
    Array.isArray(data.schemas)
  ) {
    throw new Error('contract schemas must be an object')
  }

  const seen = new Set()
  for (const route of data.routes) {
    if (route === null || typeof route !== 'object') {
      throw new Error('every route must be an object')
    }
    if (!METHODS.has(route.method)) {
      throw new Error(`unsupported route method: ${String(route.method)}`)
    }
    if (typeof route.path !== 'string' || !route.path.startsWith('/api/')) {
      throw new Error(`unsupported route path: ${String(route.path)}`)
    }
    const key = `${route.method} ${route.path}`
    if (seen.has(key)) {
      throw new Error(`duplicate route key: ${key}`)
    }
    seen.add(key)
  }

  return data
}

function literal(value) {
  return `'${String(value).replaceAll('\\', '\\\\').replaceAll("'", "\\'")}'`
}

function pascal(value) {
  return String(value)
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join('')
}

function fallbackResponseName(route) {
  const pathName = route.path
    .split('/')
    .filter(Boolean)
    .filter((part) => part !== 'api')
    .map(pascal)
    .join('')
  return `${pathName || 'Api'}${pascal(route.method)}Response`
}

function responseName(route) {
  const key = `${route.method} ${route.path}`
  return RESPONSE_TYPE_NAMES[key] ?? fallbackResponseName(route)
}

function isSimpleType(type) {
  return !type.includes(' | ') && !type.startsWith('{')
}

function withNullable(type, schema) {
  if (schema.nullable !== true) return type
  return isSimpleType(type) ? `${type} | null` : `(${type}) | null`
}

function schemaType(schema, location) {
  if (schema === null || typeof schema !== 'object' || Array.isArray(schema)) {
    throw new Error(`invalid schema at ${location}`)
  }

  if (schema.ref !== undefined) {
    if (typeof schema.ref !== 'string' || schema.ref === '') {
      throw new Error(`invalid ref at ${location}`)
    }
    return withNullable(schema.ref, schema)
  }

  if (schema.enum !== undefined) {
    if (!Array.isArray(schema.enum) || schema.enum.length === 0) {
      throw new Error(`invalid enum at ${location}`)
    }
    const union = schema.enum.map((value) => literal(value)).join(' | ')
    return withNullable(union, schema)
  }

  switch (schema.type) {
    case 'string':
      return withNullable('string', schema)
    case 'boolean':
      return withNullable('boolean', schema)
    case 'integer':
    case 'number':
      return withNullable('number', schema)
    case 'array': {
      const items = schemaType(schema.items, `${location}[]`)
      const arrayType = isSimpleType(items) ? `${items}[]` : `(${items})[]`
      return withNullable(arrayType, schema)
    }
    case 'object': {
      const fields = Object.entries(schema.fields ?? {})
      if (fields.length === 0) {
        throw new Error(`object schema at ${location} has no fields`)
      }
      const body = fields
        .map(([field, fieldSchema]) => {
          return `  ${field}: ${schemaType(fieldSchema, `${location}.${field}`)}`
        })
        .join('\n')
      return withNullable(`{\n${body}\n}`, schema)
    }
    default:
      throw new Error(`unsupported schema type at ${location}: ${String(schema.type)}`)
  }
}

function emitInterface(name, schema, location) {
  if (schema === null || typeof schema !== 'object' || schema.type !== 'object') {
    throw new Error(`interface ${name} must come from an object schema`)
  }
  const fields = Object.entries(schema.fields ?? {})
  if (fields.length === 0) {
    throw new Error(`interface ${name} has no fields`)
  }
  const lines = fields.map(([field, fieldSchema]) => {
    return `  ${field}: ${schemaType(fieldSchema, `${location}.${field}`)}`
  })
  return `export interface ${name} {\n${lines.join('\n')}\n}`
}

function generate(contract) {
  const sections = []
  sections.push(
    [
      '// Generated by frontend/scripts/generate-api-contract.mjs from',
      '// specs/001-standardize-api-responses/contracts/api-contract.json.',
      '// DO NOT EDIT. Run `npm run generate:api` after an approved contract change.',
    ].join('\n'),
  )

  sections.push(
    [
      "export type ApiMethod = 'GET' | 'POST' | 'DELETE'",
      '',
      'export interface RouteContract {',
      '  readonly method: ApiMethod',
      '  readonly path: string',
      '}',
    ].join('\n'),
  )

  const routeEntries = contract.routes.map((route) => {
    return `  ${literal(`${route.method} ${route.path}`)}: {\n    method: ${literal(route.method)},\n    path: ${literal(route.path)},\n  },`
  })
  sections.push(
    [
      'export const routes = {',
      ...routeEntries,
      '} as const satisfies Record<string, RouteContract>',
      '',
      'export type RouteKey = keyof typeof routes',
    ].join('\n'),
  )

  sections.push(
    [
      'export interface ApiErrorEnvelope {',
      '  error: {',
      '    code: string',
      '    message: string',
      '    details: unknown',
      '  }',
      '  detail: string',
      '}',
    ].join('\n'),
  )

  const codes = Object.keys(contract.errorCodes)
  sections.push(
    [
      `export const errorCodes = [${codes.map((code) => literal(code)).join(', ')}] as const`,
      '',
      'export type KnownApiErrorCode = (typeof errorCodes)[number]',
    ].join('\n'),
  )

  const statusEntries = codes.map((code) => {
    const status = contract.errorCodes[code]?.status
    if (!Number.isInteger(status)) {
      throw new Error(`error code ${code} has no integer status`)
    }
    return `  ${literal(code)}: ${status},`
  })
  sections.push(
    [
      'export const errorStatus: Record<KnownApiErrorCode, number> = {',
      ...statusEntries,
      '}',
    ].join('\n'),
  )

  for (const [name, schema] of Object.entries(contract.schemas)) {
    sections.push(emitInterface(name, schema, `schemas.${name}`))
  }

  for (const route of contract.routes) {
    const schema = route.success?.schema
    if (schema === null || schema === undefined) continue
    if (schema.ref !== undefined) continue
    if (schema.type !== 'object') {
      throw new Error(
        `route ${route.method} ${route.path} has unsupported success schema`,
      )
    }
    sections.push(
      emitInterface(
        responseName(route),
        schema,
        `routes.${route.method} ${route.path}.success.schema`,
      ),
    )
  }

  return `${sections.join('\n\n')}\n`
}

function displayPath(filePath) {
  const relativePath = relative(REPO_ROOT, filePath)
  return relativePath.startsWith('..') ? filePath : relativePath
}

function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help) {
    console.log(usage())
    return 0
  }

  const contract = loadContract(options.contract)
  const output = generate(contract)

  if (options.check) {
    let current
    try {
      current = readFileSync(options.out, 'utf8')
    } catch {
      current = null
    }
    if (current !== output) {
      console.error(
        `stale API contract: ${displayPath(options.out)} does not match ${displayPath(options.contract)}`,
      )
      return 1
    }
    console.log(`API contract is current: ${displayPath(options.out)}`)
    return 0
  }

  mkdirSync(dirname(options.out), { recursive: true })
  const temporary = `${options.out}.tmp-${process.pid}`
  writeFileSync(temporary, output, 'utf8')
  renameSync(temporary, options.out)
  console.log(`wrote ${displayPath(options.out)}`)
  return 0
}

try {
  process.exitCode = main()
} catch (error) {
  console.error(`generate-api-contract: ${error.message}`)
  process.exitCode = 1
}
