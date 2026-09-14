import test from 'node:test'
import assert from 'node:assert/strict'
import { apiErrorMessage } from './authErrors.js'

test('422 registration errors explain username and password constraints', () => {
  assert.match(apiErrorMessage({ detail: [{ loc: ['body', 'username'], msg: 'String should match pattern' }] }, 'Unprocessable Content'), /3.*80/)
  assert.match(apiErrorMessage({ detail: [{ loc: ['body', 'password'], msg: 'String too short' }] }, 'Unprocessable Content'), /6/)
})
test('business errors display their message instead of serialized detail', () => {
  assert.equal(apiErrorMessage({ error: { message: '用户名已存在', detail: '{"code":"USERNAME_EXISTS"}' } }, 'Conflict'), '用户名已存在')
})
test('unknown validation fields retain server explanation', () => {
  assert.match(apiErrorMessage({ detail: [{ loc: ['body', 'question'], msg: 'Field required' }] }, 'Unprocessable Content'), /Field required/)
})
