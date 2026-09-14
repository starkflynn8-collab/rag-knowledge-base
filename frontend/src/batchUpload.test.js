import test from 'node:test'
import assert from 'node:assert/strict'
import { buildBatchUpload } from './batchUpload.js'

test('directory upload sends file contents, relative paths and boolean flags', async () => {
  const file = new File(['hello'], 'a.txt')
  Object.defineProperty(file, 'webkitRelativePath', { value: 'docs/nested/a.txt' })
  const form = buildBatchUpload([file], { dry_run: true, include_noise_html: false })
  assert.equal(form.get('files').name, 'docs/nested/a.txt')
  assert.equal(await form.get('files').text(), 'hello')
  assert.equal(form.get('dry_run'), 'true')
  assert.equal(form.get('include_noise_html'), 'false')
})
test('empty or oversized upload rejected', () => {
  assert.throws(() => buildBatchUpload([], {}), /选择目录/)
  assert.throws(() => buildBatchUpload([{ size: 513 * 1024 * 1024 }], {}), /512 MB/)
})
