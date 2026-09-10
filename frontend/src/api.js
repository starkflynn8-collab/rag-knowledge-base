const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      ...(options.headers || {})
    },
    ...options
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || !data?.success) {
    const detail = data?.error?.detail || data?.message || response.statusText
    throw new Error(detail)
  }
  return data.data
}

export function getHealth() {
  return request('/api/health')
}

export function getConfig() {
  return request('/api/config')
}

export function switchModelMode(mode) {
  return request('/api/models/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  })
}

export function chat(payload) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export async function chatStream(payload, handlers = {}) {
  const response = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })

  if (!response.ok || !response.body) {
    throw new Error(`流式请求失败：${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''

    for (const event of events) {
      const lines = event.split('\n')
      let eventName = 'message'
      let payloadText = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventName = line.slice(7).trim()
        }
        if (line.startsWith('data: ')) {
          payloadText += line.slice(6).trim()
        }
      }
      if (!payloadText) continue
      const payloadData = JSON.parse(payloadText)
      if (eventName === 'retrieval') {
        handlers.onRetrieval?.(payloadData)
      } else if (eventName === 'token') {
        handlers.onToken?.(payloadData.text || '')
      } else if (eventName === 'done') {
        handlers.onDone?.(payloadData)
      } else if (eventName === 'error') {
        handlers.onError?.(payloadData)
      }
    }
  }
}

export function retrieve(payload) {
  return request('/api/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export function listDocuments(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value)
    }
  })
  const query = search.toString()
  return request(`/api/documents${query ? `?${query}` : ''}`)
}

export function getDocumentPreview(sourcePath) {
  const search = new URLSearchParams({ source_path: sourcePath })
  return request(`/api/documents/preview?${search.toString()}`)
}

export function getHtmlDocumentUrl(sourcePath) {
  const path = String(sourcePath || '')
    .replace(/^html[\\/]+/i, '')
    .split(/[\\/]+/)
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join('/')
  return `${BASE_URL}/api/html/${path}`
}
export function getDocumentStats() {
  return request('/api/documents/stats')
}

export async function uploadFile(file, operator = '小虎') {
  const form = new FormData()
  form.append('file', file)
  form.append('operator', operator)
  return request('/api/upload', {
    method: 'POST',
    body: form
  })
}

export function batchIngest(payload) {
  return request('/api/batch-ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export function listSessions() {
  return request('/api/sessions')
}

export function getSessionHistory(sessionId) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/history`)
}
export function clearHistory(sessionId) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/history`, {
    method: 'DELETE'
  })
}

export function updateSessionTitle(sessionId, title) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/title`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
}

export function deleteSession(sessionId) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE'
  })
}



