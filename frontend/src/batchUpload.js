export function buildBatchUpload(files, options) {
  if (!files.length) throw new Error('请先选择目录')
  if (files.length > 10000) throw new Error('单次最多上传 10000 个文件，请分批导入')
  if (files.reduce((sum, file) => sum + file.size, 0) > 512 * 1024 * 1024) {
    throw new Error('单次目录上传不能超过 512 MB，请分批导入')
  }
  const form = new FormData()
  for (const file of files) form.append('files', file, file.webkitRelativePath || file.name)
  form.append('include_noise_html', String(Boolean(options.include_noise_html)))
  form.append('dry_run', String(Boolean(options.dry_run)))
  return form
}
