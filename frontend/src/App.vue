<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <div class="brand">ZRDDS知识库</div>
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
      <section v-if="tab === 'chat'" class="panel">
        <div class="panel-head">
          <h2>问答助手</h2>
          <div class="inline-controls">
            <select v-model="chatForm.retrieval_mode">
              <option value="hybrid">hybrid</option>
              <option value="vector">vector</option>
            </select>
            <input v-model.number="chatForm.top_k" type="number" min="1" max="50" />
            <label class="toggle">
              <input v-model="streamMode" type="checkbox" />
              <span>流式</span>
            </label>
            <button class="ghost" @click="handleClearHistory" :disabled="busy">清空历史</button>
          </div>
        </div>

        <div class="messages">
          <div v-for="(msg, index) in messages" :key="index" class="message" :class="msg.role">
            <div class="role">{{ msg.role === 'user' ? '你' : '助手' }}</div>
            <pre>{{ msg.content }}</pre>
          </div>
        </div>

        <div class="composer">
          <textarea
            v-model="chatForm.question"
            placeholder="输入问题，例如：ZRDDS 的排故流程包括什么？"
            rows="4"
          />
          <div class="composer-actions">
            <input v-model="chatForm.session_id" placeholder="session_id" />
            <button @click="handleSend" :disabled="busy || !chatForm.question.trim()">
              {{ busy ? '处理中...' : '发送' }}
            </button>
          </div>
        </div>

        <div class="citations">
          <h3>引用</h3>
          <div v-if="citations.length === 0" class="empty">暂无引用</div>
          <ol v-else>
            <li v-for="item in citations" :key="item.index">
              <strong>[{{ item.index }}]</strong>
              <span>{{ item.citation }}</span>
              <div class="snippet">{{ item.snippet }}</div>
            </li>
          </ol>
        </div>
      </section>

      <section v-else-if="tab === 'docs'" class="panel">
        <div class="panel-head">
          <h2>知识库</h2>
          <div class="inline-controls">
            <input v-model="docsQuery.keyword" placeholder="按 source 搜索" />
            <input v-model="docsQuery.doc_type" placeholder="doc_type" />
            <button @click="loadDocuments">刷新</button>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat">
            <div class="label">来源数</div>
            <div class="value">{{ docStats.source_count ?? '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">Chunk 数</div>
            <div class="value">{{ docStats.chunk_count ?? '-' }}</div>
          </div>
          <div class="stat">
            <div class="label">文档数</div>
            <div class="value">{{ documents.total ?? '-' }}</div>
          </div>
        </div>

        <div class="split">
          <div>
            <h3>入库文档</h3>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>source</th>
                    <th>type</th>
                    <th>version</th>
                    <th>chunks</th>
                    <th>pages</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in documents.items" :key="item.source">
                    <td>{{ item.source }}</td>
                    <td>{{ item.doc_type }}</td>
                    <td>{{ item.version }}</td>
                    <td>{{ item.chunk_count }}</td>
                    <td>{{ item.page_count ?? '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="stack">
            <h3>单文件上传</h3>
            <input type="file" @change="onPickFile" />
            <input v-model="uploadOperator" placeholder="operator" />
            <button @click="handleUpload" :disabled="!pickedFile || busy">上传入库</button>

            <h3>批量导入</h3>
            <input v-model="batchForm.path" placeholder="后端机器本地路径" />
            <label class="toggle">
              <input v-model="batchForm.include_noise_html" type="checkbox" />
              <span>包含噪声 HTML</span>
            </label>
            <label class="toggle">
              <input v-model="batchForm.dry_run" type="checkbox" />
              <span>Dry Run</span>
            </label>
            <input v-model="batchForm.operator" placeholder="operator" />
            <button @click="handleBatchIngest" :disabled="busy">执行批量导入</button>

            <pre class="result">{{ uploadResult }}</pre>
          </div>
        </div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import {
  batchIngest,
  chat,
  chatStream,
  clearHistory,
  getConfig,
  getDocumentStats,
  getHealth,
  listDocuments,
  retrieve,
  uploadFile
} from './api.js'

const tab = ref('chat')
const busy = ref(false)
const streamMode = ref(true)
const health = reactive({})
const configData = reactive({})
const documents = reactive({ total: 0, page: 1, page_size: 20, items: [] })
const docStats = reactive({})
const citations = ref([])
const messages = ref([{ role: 'assistant', content: '你好，有什么可以帮助你？' }])
const uploadResult = ref('')
const healthOk = ref(null)
const healthLabel = computed(() => {
  if (healthOk.value === true) return '后端在线'
  if (healthOk.value === false) return '后端离线'
  return '未检测'
})
const prettyConfig = computed(() => JSON.stringify(configData, null, 2))
const pickedFile = ref(null)
const uploadOperator = ref('小虎')

const chatForm = reactive({
  question: '',
  session_id: 'user_001',
  retrieval_mode: 'hybrid',
  top_k: 5
})

const docsQuery = reactive({
  doc_type: '',
  keyword: ''
})

const batchForm = reactive({
  path: '',
  include_noise_html: false,
  dry_run: false,
  operator: '小虎'
})

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
  const data = await listDocuments({
    doc_type: docsQuery.doc_type || undefined,
    keyword: docsQuery.keyword || undefined,
    page: 1,
    page_size: 20
  })
  Object.assign(documents, data)
  const stat = await getDocumentStats()
  Object.assign(docStats, stat)
}

function onPickFile(event) {
  pickedFile.value = event.target.files?.[0] || null
}

async function handleUpload() {
  if (!pickedFile.value) return
  busy.value = true
  try {
    const res = await uploadFile(pickedFile.value, uploadOperator.value)
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

async function handleClearHistory() {
  busy.value = true
  try {
    await clearHistory(chatForm.session_id)
    messages.value = [{ role: 'assistant', content: '历史已清空' }]
    citations.value = []
  } finally {
    busy.value = false
  }
}

async function handleSend() {
  const question = chatForm.question.trim()
  if (!question) return

  messages.value.push({ role: 'user', content: question })
  chatForm.question = ''
  busy.value = true
  citations.value = []

  try {
    if (streamMode.value) {
      let answer = ''
      messages.value.push({ role: 'assistant', content: '' })
      const assistantIndex = messages.value.length - 1
      await chatStream(
        { ...chatForm, question },
        {
          onRetrieval(payload) {
            citations.value = payload.documents || []
          },
          onToken(token) {
            answer += token
            messages.value[assistantIndex].content = answer
          },
          onDone(payload) {
            if (payload?.citations) citations.value = payload.citations
            if (payload?.answer) messages.value[assistantIndex].content = payload.answer
          },
          onError(payload) {
            messages.value[assistantIndex].content = payload?.message || '流式请求失败'
          }
        }
      )
    } else {
      const res = await chat({ ...chatForm, question })
      messages.value.push({ role: 'assistant', content: res.answer })
      citations.value = res.citations || []
    }
  } catch (err) {
    messages.value.push({ role: 'assistant', content: `错误：${err.message || err}` })
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await loadStatus()
  await loadDocuments()
})
</script>

