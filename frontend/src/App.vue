<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <div class="brand">ZRDDS 知识库</div>
        <div class="subtitle">Vue + FastAPI + 本地 Ollama + 百炼</div>
      </div>
      <div class="status-chip" :class="{ ok: healthOk, bad: healthOk === false }">
        {{ healthLabel }}
      </div>
    </header>

    <nav class="tabs">
      <button :class="{ active: tab === 'chat' }" @click="tab = 'chat'">问答助手</button>
      <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'">知识库</button>
      <button :class="{ active: tab === 'status' }" @click="tab = 'status'">系统状态</button>
    </nav>

    <main class="layout">
      <section v-if="tab === 'chat'" class="panel chat-panel" :class="{ 'citations-open': citationsOpen }">
        <aside class="session-sidebar" :class="{ collapsed: sessionsCollapsed }">
          <div class="session-sidebar-head">
            <button type="button" class="ghost icon-button" @click="sessionsCollapsed = !sessionsCollapsed">
              {{ sessionsCollapsed ? '展开' : '收起' }}
            </button>
            <button v-if="!sessionsCollapsed" type="button" class="new-session" @click="handleNewSession" :disabled="busy">新对话</button>
          </div>
          <div v-if="!sessionsCollapsed" class="session-list">
            <button
              v-for="item in sessions"
              :key="item.session_id"
              type="button"
              class="session-item"
              :class="{ active: item.session_id === chatForm.session_id }"
              @click="selectSession(item.session_id)"
              :disabled="busy"
            >
              <span class="session-title">{{ item.title || item.session_id }}</span>
              <span class="session-meta">{{ item.message_count }} 条 · {{ formatSessionTime(item.updated_at) }}</span>
            </button>
            <div v-if="sessions.length === 0" class="empty session-empty">暂无历史对话</div>
          </div>
        </aside>
        <div class="chat-main">
        <div class="panel-head chat-head">
          <div>
            <h2>问答助手</h2>
            <div class="active-session">{{ activeSessionTitle }}</div>
          </div>
          <div class="inline-controls chat-controls">
            <label class="control-field">
              <span>检索模式</span>
              <select v-model="chatForm.retrieval_mode">
                <option value="hybrid">Hybrid</option>
                <option value="vector">Vector</option>
              </select>
            </label>
            <label class="control-field compact">
              <span>返回数量</span>
              <input v-model.number="chatForm.top_k" type="number" min="1" max="50" />
            </label>
            <label class="toggle stream-toggle">
              <input v-model="streamMode" type="checkbox" />
              <span>流式输出</span>
            </label>
            <button type="button" class="ghost citation-toggle" @click.stop="toggleCitations">引用 {{ citationCount }}</button>
            <button class="ghost clear-history" @click="handleClearHistory" :disabled="busy">清空历史</button>
          </div>
        </div>

        <div ref="messagesPane" class="messages chat-messages">
          <div v-for="(msg, index) in messages" :key="index" class="message" :class="msg.role">
            <div class="role">{{ msg.role === 'user' ? '你' : '助手' }}</div>
            <pre>{{ msg.content }}</pre>
          </div>
        </div>

        <div class="composer docked-composer">
          <textarea
            ref="questionInput"
            v-model="chatForm.question"
            class="question-input"
            placeholder="输入问题，例如：ZRDDS 的排故流程包括什么？"
            rows="1"
            @input="resizeQuestionInput"
            @keydown="handleQuestionKeydown"
          />
          <button class="send-button" @click="handleSend" :disabled="busy || !chatForm.question.trim()">
            {{ busy ? '处理中...' : '发送' }}
          </button>
        </div>

        </div>

        <aside v-show="citationsOpen" class="citation-sidebar open">
          <div class="citation-sidebar-head">
            <h3>引用（{{ citationCount }} 条）</h3>
            <button type="button" class="ghost sidebar-close" @click.stop="toggleCitations">收起</button>
          </div>
          <div v-if="citations.length === 0" class="empty">暂无引用</div>
          <ol v-else>
            <li v-for="item in citations" :key="item.index">
              <strong>[{{ item.index }}]</strong>
              <span>{{ item.citation }}</span>
              <div class="snippet">{{ item.snippet }}</div>
            </li>
          </ol>
        </aside>
      </section>

      <section v-else-if="tab === 'docs'" class="panel docs-panel">
        <div class="panel-head">
          <h2>知识库</h2>
          <div class="inline-controls">
            <input v-model="docsQuery.keyword" placeholder="按文件名搜索" />
            <button @click="loadDocuments">搜索</button>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat">
            <div class="label">文档数</div>
            <div class="value">{{ docStats.source_count ?? '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">Chunk 数</div>
            <div class="value">{{ docStats.chunk_count ?? '-' }}</div>
          </div>

        </div>

        <div class="split">
          <div class="docs-table-section">
            <h3>入库文档</h3>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th><button type="button" class="sort-button" @click="toggleDocumentSort('source')">文件名 <span>{{ sortIndicator('source') }}</span></button></th>
                    <th><div class="type-header"><button type="button" class="sort-button" @click="toggleDocumentSort('doc_type')">文件类型 <span>{{ sortIndicator('doc_type') }}</span></button><select v-model="selectedDocType" class="type-filter" @click.stop><option value="">全部类型</option><option v-for="type in documentTypes" :key="type" :value="type">{{ type }}</option></select></div></th>
                    <th><button type="button" class="sort-button" @click="toggleDocumentSort('chunk_count')">文本块数 <span>{{ sortIndicator('chunk_count') }}</span></button></th>
                    <th><button type="button" class="sort-button" @click="toggleDocumentSort('page_count')">页数 <span>{{ sortIndicator('page_count') }}</span></button></th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in sortedDocumentItems" :key="item.source_path || item.source">
                    <td>{{ item.source }}</td>
                    <td>{{ item.doc_type }}</td>
                    <td>{{ item.chunk_count }}</td>
                    <td>{{ item.page_count ?? '-' }}</td>
                    <td><button type="button" class="preview-button" @click="openDocumentPreview(item)" :disabled="busy">预览</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="stack">
            <h3>单文件上传</h3>
            <label class="file-drop">
              <input type="file" @change="onPickFile" />
              <span>{{ pickedFile ? pickedFile.name : '选择文件或拖动上传' }}</span>
            </label>
            <button @click="handleUpload" :disabled="!pickedFile || busy">上传入库</button>

            <h3>批量导入</h3>
            <div class="path-picker">
              <input v-model="batchForm.path" placeholder="请选择导入目录" readonly />
              <button type="button" @click="openBatchPathPicker" :disabled="busy">选择路径</button>
              <input
                ref="batchPathInput"
                class="hidden-picker"
                type="file"
                webkitdirectory
                directory
                multiple
                @change="onPickBatchPath"
              />
            </div>
            <label class="toggle">
              <input v-model="batchForm.include_noise_html" type="checkbox" />
              <span>包含噪声 HTML（导入带导航、页脚等噪声内容的 HTML 文件）</span>
            </label>
            <label class="toggle">
              <input v-model="batchForm.dry_run" type="checkbox" />
              <span>Dry Run（仅预览扫描结果，不实际写入知识库）</span>
            </label>
            <button @click="handleBatchIngest" :disabled="busy">执行批量导入</button>

            <pre class="result">{{ uploadResult }}</pre>
          </div>
        </div>

        <aside v-if="previewOpen" class="preview-sidebar" :style="{ width: `${previewWidth}px` }">
          <div class="preview-resizer" @mousedown="startPreviewResize"></div>
          <div class="preview-head">
            <div>
              <h3>{{ documentPreview.source || '文档预览' }}</h3>
              <div class="preview-meta">{{ documentPreview.doc_type || '-' }} · {{ documentPreview.chunk_count ?? 0 }} 个文本块</div>
            </div>
            <button type="button" class="ghost sidebar-close" @click="closeDocumentPreview">关闭</button>
          </div>
          <div v-if="previewLoading" class="empty preview-state">正在加载预览...</div>
          <div v-else-if="previewError" class="empty preview-state">{{ previewError }}</div>
          <div v-else class="preview-content">
            <div v-if="documentPreview.truncated" class="preview-warning">预览仅显示前 {{ documentPreview.preview_chunk_count }} 个文本块。</div>
            <section v-for="chunk in documentPreview.chunks" :key="chunk.chunk_id" class="preview-chunk">
              <div class="preview-chunk-title">Chunk {{ chunk.chunk_id }} · 页码 {{ chunk.page }}</div>
              <pre>{{ chunk.text }}</pre>
            </section>
          </div>
        </aside>
      </section>

      <section v-else class="panel">
        <div class="panel-head">
          <h2>系统状态</h2>
          <div class="inline-controls">
            <button @click="loadStatus">刷新</button>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat">
            <div class="label">Embedding</div>
            <div class="value">{{ health.embedding?.model || '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">LLM</div>
            <div class="value">{{ health.llm?.model || '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">Rerank</div>
            <div class="value">{{ health.rerank?.model || '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">默认检索</div>
            <div class="value">{{ health.retrieval?.default_mode || '-' }}</div>
          </div>
        </div>

        <pre class="result">{{ prettyConfig }}</pre>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  batchIngest,
  chat,
  chatStream,
  clearHistory,
  getConfig,
  getDocumentStats,
  getDocumentPreview,
  getHealth,
  getSessionHistory,
  listDocuments,
  listSessions,
  uploadFile
} from './api.js'

const tab = ref('chat')
const busy = ref(false)
const streamMode = ref(true)
const questionInput = ref(null)
const messagesPane = ref(null)
const health = reactive({})
const configData = reactive({})
const documents = reactive({ total: 0, page: 1, page_size: 200, items: [] })
const documentPreview = reactive({ source: '', source_path: '', doc_type: '', chunk_count: 0, preview_chunk_count: 0, truncated: false, chunks: [] })
const previewOpen = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewWidth = ref(720)
const previewResizeState = { active: false, startX: 0, startWidth: 0 }
const documentSort = reactive({ key: 'source', direction: 'asc' })
const selectedDocType = ref('')
const docStats = reactive({})
const citations = ref([])
const citationCount = ref(0)
const citationsOpen = ref(false)
const sessions = ref([])
const sessionsCollapsed = ref(false)
const messages = ref(initialMessages())
const uploadResult = ref('')
const healthOk = ref(null)
const healthLabel = computed(() => {
  if (healthOk.value === true) return '后端在线'
  if (healthOk.value === false) return '后端离线'
  return '未检测'
})
const prettyConfig = computed(() => JSON.stringify(configData, null, 2))
const pickedFile = ref(null)
const batchPathInput = ref(null)

const chatForm = reactive({
  question: '',
  session_id: 'user_001',
  retrieval_mode: 'hybrid',
  top_k: 5
})

const documentTypes = computed(() => {
  return [...new Set(documents.items.map((item) => item.doc_type).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b), 'zh-CN', { numeric: true, sensitivity: 'base' })
  )
})

const filteredDocumentItems = computed(() => {
  if (!selectedDocType.value) return documents.items
  return documents.items.filter((item) => item.doc_type === selectedDocType.value)
})
const sortedDocumentItems = computed(() => {
  const direction = documentSort.direction === 'desc' ? -1 : 1
  return [...filteredDocumentItems.value].sort((a, b) => compareDocumentValue(a, b, documentSort.key) * direction)
})
const activeSessionTitle = computed(() => {
  const current = sessions.value.find((item) => item.session_id === chatForm.session_id)
  return current?.title || chatForm.session_id
})

const docsQuery = reactive({
  keyword: ''
})

const batchForm = reactive({
  path: '',
  include_noise_html: false,
  dry_run: false
})

function compareDocumentValue(a, b, key) {
  const left = a?.[key]
  const right = b?.[key]
  if (key === 'chunk_count' || key === 'page_count') {
    const leftNumber = Number.isFinite(Number(left)) ? Number(left) : -1
    const rightNumber = Number.isFinite(Number(right)) ? Number(right) : -1
    return leftNumber - rightNumber
  }
  return String(left ?? '').localeCompare(String(right ?? ''), 'zh-CN', { numeric: true, sensitivity: 'base' })
}

function toggleDocumentSort(key) {
  if (documentSort.key === key) {
    documentSort.direction = documentSort.direction === 'asc' ? 'desc' : 'asc'
    return
  }
  documentSort.key = key
  documentSort.direction = 'asc'
}

function sortIndicator(key) {
  if (documentSort.key !== key) return ''
  return documentSort.direction === 'asc' ? '▲' : '▼'
}
function initialMessages() {
  return [{ role: 'assistant', content: '你好，有什么可以帮助你？' }]
}

function createSessionId() {
  return `session_${Date.now()}`
}

function formatSessionTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadSessions() {
  try {
    const data = await listSessions()
    sessions.value = Array.isArray(data.items) ? data.items : []
  } catch {
    sessions.value = []
  }
}

async function selectSession(sessionId) {
  if (!sessionId || busy.value) return
  busy.value = true
  try {
    chatForm.session_id = sessionId
    const data = await getSessionHistory(sessionId)
    messages.value = Array.isArray(data.messages) && data.messages.length > 0 ? data.messages : initialMessages()
    setCitations([])
    await nextTick()
    scrollMessagesToBottom()
    resizeQuestionInput()
  } catch (err) {
    messages.value = [{ role: 'assistant', content: `加载历史失败：${err.message || err}` }]
  } finally {
    busy.value = false
  }
}

function handleNewSession() {
  if (busy.value) return
  chatForm.session_id = createSessionId()
  chatForm.question = ''
  messages.value = initialMessages()
  setCitations([])
  nextTick(() => {
    resizeQuestionInput()
    scrollMessagesToBottom()
  })
}
async function loadStatus() {
  try {
    const data = await getHealth()
    Object.assign(health, data)
    healthOk.value = true
  } catch (err) {
    healthOk.value = false
  }

  try {
    const conf = await getConfig()
    Object.assign(configData, conf)
  } catch {}
}

async function loadDocuments() {
  const pageSize = 200
  const baseParams = {
    keyword: docsQuery.keyword || undefined,
    page_size: pageSize
  }
  const firstPage = await listDocuments({ ...baseParams, page: 1 })
  const items = Array.isArray(firstPage.items) ? [...firstPage.items] : []
  const total = Number(firstPage.total) || items.length
  const pageCount = Math.ceil(total / pageSize)

  for (let page = 2; page <= pageCount; page += 1) {
    const data = await listDocuments({ ...baseParams, page })
    if (Array.isArray(data.items)) items.push(...data.items)
  }

  Object.assign(documents, {
    ...firstPage,
    page: 1,
    page_size: pageSize,
    total,
    items
  })
  const stat = await getDocumentStats()
  Object.assign(docStats, stat)
}

function clampPreviewWidth(value) {
  const maxWidth = Math.max(420, Math.floor(window.innerWidth * 0.82))
  return Math.min(maxWidth, Math.max(480, value))
}

function startPreviewResize(event) {
  previewResizeState.active = true
  previewResizeState.startX = event.clientX
  previewResizeState.startWidth = previewWidth.value
  document.body.classList.add('is-resizing-preview')
  window.addEventListener('mousemove', resizePreview)
  window.addEventListener('mouseup', stopPreviewResize)
}

function resizePreview(event) {
  if (!previewResizeState.active) return
  const delta = previewResizeState.startX - event.clientX
  previewWidth.value = clampPreviewWidth(previewResizeState.startWidth + delta)
}

function stopPreviewResize() {
  previewResizeState.active = false
  document.body.classList.remove('is-resizing-preview')
  window.removeEventListener('mousemove', resizePreview)
  window.removeEventListener('mouseup', stopPreviewResize)
}
async function openDocumentPreview(item) {
  if (!item?.source_path) return
  previewOpen.value = true
  previewLoading.value = true
  previewError.value = ''
  Object.assign(documentPreview, { source: item.source, source_path: item.source_path, doc_type: item.doc_type, chunk_count: item.chunk_count, preview_chunk_count: 0, truncated: false, chunks: [] })
  try {
    const data = await getDocumentPreview(item.source_path)
    Object.assign(documentPreview, data)
  } catch (err) {
    previewError.value = `加载预览失败：${err.message || err}`
  } finally {
    previewLoading.value = false
  }
}

function closeDocumentPreview() {
  previewOpen.value = false
}
function onPickFile(event) {
  pickedFile.value = event.target.files?.[0] || null
}

function openBatchPathPicker() {
  batchPathInput.value?.click()
}

function onPickBatchPath(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const relativePath = file.webkitRelativePath || file.name
  batchForm.path = file.path || relativePath.split('/')[0] || ''
}

async function handleUpload() {
  if (!pickedFile.value) return
  busy.value = true
  try {
    const res = await uploadFile(pickedFile.value)
    uploadResult.value = JSON.stringify(res, null, 2)
    await loadDocuments()
  } catch (err) {
    uploadResult.value = String(err.message || err)
  } finally {
    busy.value = false
  }
}

async function handleBatchIngest() {
  busy.value = true
  try {
    const res = await batchIngest(batchForm)
    uploadResult.value = JSON.stringify(res, null, 2)
    await loadDocuments()
  } catch (err) {
    uploadResult.value = String(err.message || err)
  } finally {
    busy.value = false
  }
}

function normalizeTopK(value) {
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return 5
  return Math.min(50, Math.max(1, parsed))
}

function buildChatPayload(question) {
  const topK = normalizeTopK(chatForm.top_k)
  chatForm.top_k = topK
  return {
    question,
    session_id: chatForm.session_id,
    retrieval_mode: chatForm.retrieval_mode,
    top_k: topK,
    return_context: true
  }
}

function setCitations(items, count) {
  citations.value = Array.isArray(items) ? items : []
  citationCount.value = Number.isInteger(count) ? count : citations.value.length
}

function toggleCitations() {
  citationsOpen.value = !citationsOpen.value
}

function scrollMessagesToBottom() {
  const el = messagesPane.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function resizeQuestionInput() {
  const el = questionInput.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

async function handleClearHistory() {
  busy.value = true
  try {
    await clearHistory(chatForm.session_id)
    messages.value = [{ role: 'assistant', content: '历史已清空' }]
    setCitations([])
  } finally {
    busy.value = false
  }
}

function handleQuestionKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  if (!busy.value && chatForm.question.trim()) {
    handleSend()
  }
}

async function handleSend() {
  const question = chatForm.question.trim()
  if (!question) return

  messages.value.push({ role: 'user', content: question })
  chatForm.question = ''
  nextTick(resizeQuestionInput)
  busy.value = true
  setCitations([])

  try {
    if (streamMode.value) {
      let answer = ''
      messages.value.push({ role: 'assistant', content: '' })
      const assistantIndex = messages.value.length - 1
      await chatStream(
        buildChatPayload(question),
        {
          onRetrieval(payload) {
            setCitations(payload.documents, payload.citation_count)
          },
          onToken(token) {
            answer += token
            messages.value[assistantIndex].content = answer
            nextTick(scrollMessagesToBottom)
          },
          onDone(payload) {
            if (payload?.citations) setCitations(payload.citations, payload.citation_count)
            if (payload?.answer) messages.value[assistantIndex].content = payload.answer
            nextTick(scrollMessagesToBottom)
          },
          onError(payload) {
            messages.value[assistantIndex].content = payload?.message || '流式请求失败'
          }
        }
      )
    } else {
      const res = await chat(buildChatPayload(question))
      messages.value.push({ role: 'assistant', content: res.answer })
      await nextTick()
      scrollMessagesToBottom()
      setCitations(res.citations, res.citation_count)
    }
  } catch (err) {
    messages.value.push({ role: 'assistant', content: `错误：${err.message || err}` })
    await nextTick()
    scrollMessagesToBottom()
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => {
  stopPreviewResize()
})

onMounted(async () => {
  await loadStatus()
  await loadSessions()
  await loadDocuments()
  await nextTick()
  resizeQuestionInput()
})
</script>
























