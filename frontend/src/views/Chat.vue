<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="mini-chop" aria-hidden="true">
          <svg viewBox="0 0 32 32" fill="none">
            <rect x="1.5" y="1.5" width="29" height="29" rx="2" stroke="currentColor" stroke-width="2"/>
            <text x="16" y="22" text-anchor="middle" fill="currentColor" font-size="13" font-weight="900" font-family="serif">智</text>
          </svg>
        </div>
        <span class="sidebar-title">PersonalAgent</span>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/chat" class="nav-item active">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          对话
        </router-link>
        <router-link to="/knowledge" class="nav-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          知识库
        </router-link>
      </nav>

      <div class="sidebar-body">
        <button class="new-chat-btn" @click="handleNewChat" :disabled="loadingSessions">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          新对话
        </button>

        <div class="session-list" v-if="sessions.length > 0">
          <div
            v-for="s in sessions" :key="s.session_id"
            class="session-item"
            :class="{ current: s.session_id === currentSessionId }"
            @click="switchSession(s.session_id)"
          >
            <span class="session-title">{{ s.title }}</span>
            <span class="session-mode">{{ s.mode === 'rag' ? 'RAG' : '' }}</span>
            <button class="session-delete" @click.stop="handleDeleteSession(s.session_id)" title="删除">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>
        <p class="empty-hint" v-else>暂无对话</p>
      </div>

      <div class="sidebar-footer">
        <div class="user-row">
          <div class="user-avatar">{{ userInitial }}</div>
          <span class="user-name">{{ user?.nickname || user?.username }}</span>
        </div>
        <button class="logout-link" @click="handleLogout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </aside>

    <!-- Main -->
    <main class="main-area">
      <!-- Empty state -->
      <div class="welcome" v-if="!currentSessionId">
        <div class="welcome-icon">
          <svg viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="22" stroke="currentColor" stroke-width="1.5" opacity="0.2"/>
            <circle cx="24" cy="24" r="16" stroke="currentColor" stroke-width="1" opacity="0.3"/>
            <circle cx="24" cy="24" r="6" fill="currentColor" opacity="0.7"/>
            <path d="M24 2v8M24 38v8M2 24h8M38 24h8" stroke="currentColor" stroke-width="1.5" opacity="0.15"/>
          </svg>
        </div>
        <h1>下午好，{{ user?.nickname || user?.username }}</h1>
        <p class="welcome-sub">开始一段新对话，或从左侧选择历史会话</p>
        <button class="start-btn" @click="handleNewChat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          开始新对话
        </button>
      </div>

      <!-- Chat area -->
      <div class="chat-area" v-else>
        <!-- Header -->
        <div class="chat-header">
          <h2>{{ currentTitle }}</h2>
        </div>

        <!-- Messages -->
        <div class="msg-list" ref="msgList">
          <div
            v-for="(msg, idx) in messages" :key="idx"
            class="msg-row"
            :class="msg.role"
          >
            <div class="msg-avatar">
              <span v-if="msg.role === 'user'">{{ userInitial }}</span>
              <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <rect x="1.5" y="1.5" width="21" height="21" rx="3" stroke="currentColor" stroke-width="1.5"/>
                <text x="12" y="16" text-anchor="middle" fill="currentColor" font-size="10" font-weight="900">智</text>
              </svg>
            </div>
            <div class="msg-bubble">
              <div class="msg-text">{{ msg.content }}</div>
              <div class="msg-sources" v-if="msg.metadata?.sources?.length">
                <span class="source-tag" v-for="src in msg.metadata.sources" :key="src">{{ src }}</span>
              </div>
            </div>
          </div>

          <!-- Streaming message -->
          <div class="msg-row assistant" v-if="streaming">
            <div class="msg-avatar">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <rect x="1.5" y="1.5" width="21" height="21" rx="3" stroke="currentColor" stroke-width="1.5"/>
                <text x="12" y="16" text-anchor="middle" fill="currentColor" font-size="10" font-weight="900">智</text>
              </svg>
            </div>
            <div class="msg-bubble">
              <div class="msg-text">{{ streamText }}<span v-if="!streamText" class="thinking-dots"><i>.</i><i>.</i><i>.</i></span></div>
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="input-area">
          <div class="input-hint" v-if="!wsReady && currentSessionId">正在连接服务器...</div>
          <div class="input-row">
            <textarea
              v-model="inputText"
              class="chat-input"
              :placeholder="wsReady ? '输入消息，Enter 发送，Shift+Enter 换行' : '正在连接...'"
              rows="1"
              :disabled="loading || !wsReady"
              @keydown.enter.exact.prevent="handleSend"
              @input="autoResize"
              ref="inputEl"
            ></textarea>
            <button class="send-btn" @click="handleSend" :disabled="loading || !wsReady || !inputText.trim()">
              <svg v-if="!loading" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
              <span v-else class="mini-spinner"></span>
            </button>
          </div>
          <div class="input-toolbar">
            <div class="mode-switch">
              <button :class="{ active: currentMode === 'normal' }" @click="switchMode('normal')">普通模式</button>
              <button :class="{ active: currentMode === 'rag' }" @click="switchMode('rag')">RAG 增强</button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <ConfirmModal
      :visible="showDeleteModal"
      title="删除会话"
      message="确认删除此会话？相关的所有消息将被清除，此操作不可撤销。"
      :loading="deletingLoading"
      @confirm="confirmDeleteSession"
      @cancel="showDeleteModal = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  createSession, getSessionList, deleteSession, getMessageHistory, createChatWebSocket,
} from '../api/index.js'
import ConfirmModal from '../components/ConfirmModal.vue'

const router = useRouter()

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
})
const userInitial = computed(() => (user.value?.nickname || user.value?.username || '?')[0])

// Session state
const sessions = ref([])
const currentSessionId = ref(null)
const currentTitle = ref('')
const currentMode = ref('rag')
const loadingSessions = ref(false)

// Message state
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')

let ws = null
const wsReady = ref(false)
const msgList = ref(null)
const inputEl = ref(null)

// Delete confirm modal
const showDeleteModal = ref(false)
const deletingSessionId = ref(null)
const deletingLoading = ref(false)

// Init
onMounted(() => fetchSessions())

function scrollBottom() {
  nextTick(() => {
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  })
}

// ==================== Sessions ====================

async function fetchSessions() {
  loadingSessions.value = true
  try {
    const res = await getSessionList()
    if (res.code === 0) sessions.value = res.data.items
  } catch (e) { console.error(e) }
  finally { loadingSessions.value = false }
}

async function handleNewChat() {
  loading.value = false
  streaming.value = false
  streamText.value = ''
  messages.value = []
  disconnectWs()
  currentSessionId.value = null
  currentTitle.value = ''
  currentMode.value = 'rag'

  try {
    const res = await createSession('新对话', 'rag')
    if (res.code === 0) {
      currentSessionId.value = res.data.session_id
      currentTitle.value = res.data.title
      await fetchSessions()
      connectWs(res.data.session_id)
    }
  } catch (e) { console.error(e) }
}

async function switchSession(sid) {
  if (sid === currentSessionId.value) return
  disconnectWs()
  messages.value = []
  streamText.value = ''
  streaming.value = false
  loading.value = false
  currentSessionId.value = sid

  const s = sessions.value.find(x => x.session_id === sid)
  if (s) {
    currentTitle.value = s.title
    currentMode.value = 'rag'
  }

  // Load history
  try {
    const res = await getMessageHistory(sid)
    if (res.code === 0) {
      messages.value = res.data.items.map(m => ({
        role: m.role,
        content: m.content,
        metadata: m.metadata,
      }))
      scrollBottom()
    }
  } catch (e) { console.error(e) }

  connectWs(sid)
}

function handleDeleteSession(sid) {
  deletingSessionId.value = sid
  showDeleteModal.value = true
}

async function confirmDeleteSession() {
  const sid = deletingSessionId.value
  if (!sid) return
  deletingLoading.value = true
  try {
    await deleteSession(sid)
    if (currentSessionId.value === sid) {
      disconnectWs()
      currentSessionId.value = null
      messages.value = []
    }
    await fetchSessions()
  } catch (e) { console.error(e) }
  finally {
    deletingLoading.value = false
    showDeleteModal.value = false
    deletingSessionId.value = null
  }
}

// ==================== WebSocket ====================

function connectWs(sid) {
  disconnectWs()
  wsReady.value = false
  try {
    ws = createChatWebSocket(sid)
    ws.onopen = () => {
      console.log('WS connected')
      wsReady.value = true
    }
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'token') {
        streamText.value += data.data
        scrollBottom()
      } else if (data.type === 'title') {
        currentTitle.value = data.data
        fetchSessions()
      } else if (data.type === 'done') {
        finishMessage(data.data?.sources || [])
      } else if (data.type === 'error') {
        loading.value = false
        streaming.value = false
        alert(data.data?.message || '发生错误')
      }
    }
    ws.onclose = () => { console.log('WS disconnected'); wsReady.value = false }
    ws.onerror = () => { loading.value = false; streaming.value = false; wsReady.value = false }
  } catch (e) {
    console.error('WS connect failed', e)
    wsReady.value = false
  }
}

function disconnectWs() {
  wsReady.value = false
  if (ws) {
    try { ws.close() } catch (e) { /* ignore */ }
    ws = null
  }
}

// ==================== Messages ====================

function handleSend() {
  if (!wsReady.value) return  // WS 未连接
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  streamText.value = ''
  streaming.value = true
  loading.value = true
  inputText.value = ''
  autoResize()
  scrollBottom()

  ws.send(JSON.stringify({ type: 'chat', content: text, mode: currentMode.value }))
}

function finishMessage(sources) {
  const meta = { mode: currentMode.value }
  if (sources?.length) meta.sources = sources
  messages.value.push({ role: 'assistant', content: streamText.value, metadata: meta })
  streamText.value = ''
  streaming.value = false
  loading.value = false
  scrollBottom()
}

function switchMode(mode) {
  currentMode.value = mode
}

function autoResize() {
  nextTick(() => {
    const el = inputEl.value
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    }
  })
}

function handleLogout() {
  disconnectWs()
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.chat-layout { display: flex; height: 100vh; background: var(--paper); }

/* ==================== Sidebar ==================== */
.sidebar {
  width: 272px; background: var(--ink-deep); color: var(--paper-warm);
  display: flex; flex-direction: column; flex-shrink: 0;
  border-right: 1px solid rgba(255,255,255,0.04);
}
.sidebar-header {
  padding: 22px 20px; display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.mini-chop { color: var(--vermillion); width: 28px; flex-shrink: 0; }
.sidebar-title {
  font-family: var(--font-display); font-size: 15px; font-weight: 700;
  letter-spacing: 0.04em; color: var(--paper);
}
.sidebar-nav {
  padding: 12px 12px; display: flex; flex-direction: column; gap: 4px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 6px;
  color: var(--stone-light); text-decoration: none; font-size: 13px;
  letter-spacing: 0.04em; transition: all 0.2s;
}
.nav-item:hover { background: rgba(255,255,255,0.05); color: var(--paper); }
.nav-item.active { background: rgba(255,255,255,0.08); color: var(--paper); }

.sidebar-body { flex: 1; padding: 12px; overflow-y: auto; }

.new-chat-btn {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 10px 14px; background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 6px;
  color: var(--paper-warm); font-size: 13px; font-family: var(--font-body);
  cursor: pointer; transition: all 0.2s; letter-spacing: 0.04em;
}
.new-chat-btn:hover { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.15); }
.new-chat-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.session-list { margin-top: 8px; display: flex; flex-direction: column; gap: 2px; }
.session-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-radius: 6px; cursor: pointer; transition: all 0.15s;
  color: var(--stone-light); font-size: 13px;
}
.session-item:hover { background: rgba(255,255,255,0.05); }
.session-item.current { background: rgba(255,255,255,0.08); color: var(--paper); }
.session-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-mode { font-size: 10px; color: var(--vermillion); font-weight: 600; letter-spacing: 0.06em; }
.session-delete {
  background: none; border: none; color: transparent; cursor: pointer; padding: 2px;
  transition: color 0.2s; display: flex;
}
.session-item:hover .session-delete { color: var(--stone); }
.session-delete:hover { color: var(--vermillion) !important; }

.empty-hint { text-align: center; color: var(--stone); font-size: 13px; margin-top: 32px; }

.sidebar-footer {
  padding: 14px 20px; border-top: 1px solid rgba(255,255,255,0.06);
  display: flex; align-items: center; justify-content: space-between;
}
.user-row { display: flex; align-items: center; gap: 10px; }
.user-avatar {
  width: 30px; height: 30px; border-radius: 2px; background: var(--vermillion);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; font-family: var(--font-display);
}
.user-name { font-size: 13px; color: var(--stone-light); letter-spacing: 0.04em; }
.logout-link { background: none; border: none; color: var(--stone); cursor: pointer; padding: 4px; border-radius: 3px; transition: color 0.2s; display: flex; }
.logout-link:hover { color: var(--vermillion); }

/* ==================== Welcome ==================== */
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.welcome {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  animation: welcome-in 0.7s ease both;
}
@keyframes welcome-in { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.welcome-icon { width: 64px; margin-bottom: 28px; color: var(--stone-light); }
.welcome h1 { font-family: var(--font-display); font-size: 28px; font-weight: 700; color: var(--ink-black); margin-bottom: 8px; }
.welcome-sub { color: var(--stone); font-size: 15px; margin-bottom: 28px; }
.start-btn {
  display: flex; align-items: center; gap: 8px; padding: 12px 28px;
  background: var(--vermillion); color: #fff; border: none; border-radius: 3px;
  font-size: 15px; font-family: var(--font-body); cursor: pointer;
  transition: background 0.25s;
}
.start-btn:hover { background: var(--vermillion-hover); }

/* ==================== Chat area ==================== */
.chat-area {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: radial-gradient(ellipse at 40% 30%, rgba(139,133,128,0.03) 0%, transparent 55%), var(--paper);
}
.chat-header {
  padding: 16px 24px; display: flex; align-items: center;
  border-bottom: 1px solid var(--border-subtle); flex-shrink: 0;
}
.chat-header h2 {
  font-family: var(--font-display); font-size: 18px; font-weight: 700; color: var(--ink-black);
  max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ==================== Messages ==================== */
.msg-list { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }

.msg-row { display: flex; gap: 12px; max-width: 80%; }
.msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
.msg-row.assistant { align-self: flex-start; }

.msg-avatar {
  width: 32px; height: 32px; border-radius: 3px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; font-family: var(--font-display);
}
.msg-row.user .msg-avatar { background: var(--vermillion); color: #fff; }
.msg-row.assistant .msg-avatar { background: var(--jade); color: #fff; }

.msg-bubble {
  padding: 12px 16px; border-radius: 6px; line-height: 1.7; font-size: 14px;
}
.msg-row.user .msg-bubble { background: var(--ink-black); color: var(--paper); }
.msg-row.assistant .msg-bubble { background: #fff; color: var(--ink-black); border: 1px solid var(--border-subtle); }

.msg-text { white-space: pre-wrap; word-break: break-word; }

.thinking-dots { display: inline-flex; gap: 2px; align-items: flex-end; padding-left: 2px; }
.thinking-dots i {
  display: inline-block; width: 4px; height: 4px; border-radius: 50%;
  background: var(--stone-light);
  animation: dotPulse 1.4s ease-in-out infinite;
}
.thinking-dots i:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.2; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

.msg-sources { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.source-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 3px;
  background: var(--jade-light); color: var(--jade); font-weight: 500;
}

/* ==================== Input ==================== */
.input-area {
  padding: 12px 24px 14px; border-top: 1px solid var(--border-subtle);
  flex-shrink: 0; background: rgba(255,255,255,0.5);
}
.input-hint {
  font-size: 12px; color: var(--vermillion); text-align: center;
  margin-bottom: 8px; letter-spacing: 0.04em;
}
.input-row {
  display: flex; gap: 10px; align-items: flex-end;
}
.chat-input {
  flex: 1; border: 1px solid var(--border-subtle); border-radius: 8px;
  padding: 11px 16px; font-size: 15px; font-family: var(--font-body);
  color: var(--ink-black); background: #fff; outline: none; resize: none;
  line-height: 1.6; max-height: 160px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.chat-input:focus {
  border-color: var(--ink-black);
  box-shadow: 0 0 0 3px rgba(0,0,0,0.04);
}
.chat-input:disabled { opacity: 0.5; background: #f9f9f9; }

.send-btn {
  width: 42px; height: 42px; border-radius: 8px; border: none;
  background: var(--ink-black); color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s, transform 0.15s; flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { background: var(--vermillion); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.input-toolbar {
  display: flex; align-items: center; justify-content: flex-start;
  margin-top: 10px;
}

.mode-switch {
  display: flex; gap: 4px;
  background: rgba(0,0,0,0.04); border-radius: 6px; padding: 3px;
}
.mode-switch button {
  padding: 5px 14px; border: none; border-radius: 4px;
  background: transparent; font-size: 12px; font-family: var(--font-body);
  cursor: pointer; color: var(--stone); transition: all 0.2s;
  letter-spacing: 0.04em;
}
.mode-switch button.active {
  background: #fff; color: var(--ink-black);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.mode-switch button:not(.active):hover { color: var(--ink-black); }

.mini-spinner {
  width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) {
  .sidebar { width: 64px; }
  .sidebar-title, .user-name, .nav-item span, .new-chat-btn span,
  .session-title, .session-mode, .session-delete, .empty-hint { display: none; }
  .nav-item, .new-chat-btn { justify-content: center; padding: 10px; }
  .sidebar-header { justify-content: center; }
  .msg-row { max-width: 92%; }
}
</style>
