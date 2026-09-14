export function apiErrorMessage(data, fallback) {
  if (Array.isArray(data?.detail)) {
    const hints = {
      username: '用户名须为 3–80 位英文字母、数字、下划线、点或短横线',
      password: '密码长度须为 6–200 位',
      display_name: '显示名称不能超过 80 位'
    }
    return data.detail.map((item) => hints[item.loc?.at(-1)] || item.msg || '输入参数不符合要求').join('；')
  }
  return data?.error?.message || data?.error?.detail || data?.message || (typeof data?.detail === 'string' ? data.detail : '') || fallback || '请求失败'
}
