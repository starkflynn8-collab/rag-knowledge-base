import test from 'node:test'
import assert from 'node:assert/strict'
import { probeSession } from './backendReadiness.js'

test('unreachable backend can recover without treating outage as logout', async () => {
  assert.equal((await probeSession(async () => { throw new TypeError('Failed to fetch') })).ready, false)
  const user = { id: 1 }
  assert.deepEqual(await probeSession(async () => user), { ready: true, user })
})
test('401 means backend ready, login required', async () => {
  assert.deepEqual(await probeSession(async () => { throw Object.assign(new Error(), { status: 401 }) }), { ready: true, user: null })
})
test('server errors are not mistaken for a valid session', async () => {
  assert.equal((await probeSession(async () => { throw Object.assign(new Error(), { status: 503 }) })).ready, false)
})
