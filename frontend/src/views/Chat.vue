<template>
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
    <div class="chat-header">
      <h2>{{ currentTitle }}</h2>
    </div>

    <div class="msg-list" ref="msgList">
      <div v-for="(msg, idx) in messages" :key="idx" class="msg-row" :class="msg.role">
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
        <span class="intent-badge" v-if="lastIntent" :class="lastIntent">
          {{ intentLabel(lastIntent) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { createSession, getMessageHistory, streamChatMessage } from '../api/index.js'

const router = useRouter()
const route = useRoute()

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
})
const userInitial = computed(() => (user.value?.nickname || user.value?.username || '?')[0])

const currentSessionId = ref(null)
const currentTitle = ref('')
const lastIntent = ref('')
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
let streamController = null
const wsReady = ref(true)
const msgList = ref(null)
const inputEl = ref(null)

// 监听路由 query 变化，加载对应会话
watch(() => route.query.sid, async (sid) => {
  if (sid && sid !== currentSessionId.value) {
    await switchSession(sid)
  }
}, { immediate: true })

onUnmounted(() => { disconnectWs() })

async function handleNewChat() {
  loading.value = false; streaming.value = false; streamText.value = ''
  messages.value = []; disconnectWs()
  currentSessionId.value = null; currentTitle.value = ''; lastIntent.value = ''
  try {
    const res = await createSession('新对话')
    if (res.code === 0) {
      currentSessionId.value = res.data.session_id
      currentTitle.value = res.data.title
      connectWs(res.data.session_id)
    }
  } catch (e) { console.error(e) }
}

async function switchSession(sid) {
  if (sid === currentSessionId.value) return
  disconnectWs(); messages.value = []; streamText.value = ''
  streaming.value = false; loading.value = false
  currentSessionId.value = sid; lastIntent.value = ''
  try {
    const res = await getMessageHistory(sid)
    if (res.code === 0) {
      messages.value = res.data.items.map(m => ({ role: m.role, content: m.content, metadata: m.metadata }))
      scrollBottom()
    }
  } catch (e) { console.error(e) }
  connectWs(sid)
}

function connectWs(sid) {
  disconnectWs()
  wsReady.value = Boolean(sid)
}

function disconnectWs() {
  if (streamController) {
    try { streamController.abort() } catch {}
    streamController = null
  }
}

async function handleSend() {
  if (!wsReady.value) return
  const text = inputText.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  streamText.value = ''; streaming.value = true; loading.value = true
  inputText.value = ''; autoResize(); scrollBottom()
  streamController = new AbortController()
  try {
    await streamChatMessage(currentSessionId.value, text, {
      token: (data) => { streamText.value += data; scrollBottom() },
      title: (data) => { currentTitle.value = data },
      done: (data) => { finishMessage(data?.sources || []); lastIntent.value = data?.intent || '' },
      error: (data) => {
        loading.value = false
        streaming.value = false
        alert(data?.message || '发生错误')
      },
    }, streamController.signal)
  } catch (e) {
    if (e.name !== 'AbortError') {
      loading.value = false
      streaming.value = false
      alert(e.message || '发生错误')
    }
  } finally {
    streamController = null
  }
}

function finishMessage(sources) {
  const meta = {}; if (sources?.length) meta.sources = sources
  messages.value.push({ role: 'assistant', content: streamText.value, metadata: meta })
  streamText.value = ''; streaming.value = false; loading.value = false; scrollBottom()
}

function intentLabel(i) {
  const map = { chat: '通用问答', rag: '知识库检索' }
  return map[i] || i
}
function autoResize() { nextTick(() => { const el = inputEl.value; if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px' } }) }
function scrollBottom() { nextTick(() => { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight }) }
</script>

<style scoped>
.welcome {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  animation: welcome-in 0.7s ease both;
  background: radial-gradient(ellipse at 40% 30%, rgba(139,133,128,0.03) 0%, transparent 55%), var(--paper);
}
@keyframes welcome-in { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.welcome-icon { width: 64px; margin-bottom: 28px; color: var(--stone-light); }
.welcome h1 { font-family: var(--font-display); font-size: 28px; font-weight: 700; color: var(--ink-black); margin-bottom: 8px; }
.welcome-sub { color: var(--stone); font-size: 15px; margin-bottom: 28px; }
.start-btn { display: flex; align-items: center; gap: 8px; padding: 12px 28px; background: var(--vermillion); color: #fff; border: none; border-radius: 3px; font-size: 15px; font-family: var(--font-body); cursor: pointer; transition: background 0.25s; }
.start-btn:hover { background: var(--vermillion-hover); }

.chat-area {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: radial-gradient(ellipse at 40% 30%, rgba(139,133,128,0.03) 0%, transparent 55%), var(--paper);
}
.chat-header { padding: 16px 24px; display: flex; align-items: center; border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
.chat-header h2 { font-family: var(--font-display); font-size: 18px; font-weight: 700; color: var(--ink-black); max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.msg-list { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.msg-row { display: flex; gap: 12px; max-width: 80%; }
.msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
.msg-row.assistant { align-self: flex-start; }
.msg-avatar { width: 32px; height: 32px; border-radius: 3px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; font-family: var(--font-display); }
.msg-row.user .msg-avatar { background: var(--vermillion); color: #fff; }
.msg-row.assistant .msg-avatar { background: var(--jade); color: #fff; }
.msg-bubble { padding: 12px 16px; border-radius: 6px; line-height: 1.7; font-size: 14px; }
.msg-row.user .msg-bubble { background: var(--ink-black); color: var(--paper); }
.msg-row.assistant .msg-bubble { background: #fff; color: var(--ink-black); border: 1px solid var(--border-subtle); }
.msg-text { white-space: pre-wrap; word-break: break-word; }
.msg-sources { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.source-tag { font-size: 11px; padding: 2px 8px; border-radius: 3px; background: var(--jade-light); color: var(--jade); font-weight: 500; }

.thinking-dots { display: inline-flex; gap: 2px; align-items: flex-end; padding-left: 2px; }
.thinking-dots i { display: inline-block; width: 4px; height: 4px; border-radius: 50%; background: var(--stone-light); animation: dotPulse 1.4s ease-in-out infinite; }
.thinking-dots i:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse { 0%, 80%, 100% { opacity: 0.2; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

.input-area { padding: 12px 24px 14px; border-top: 1px solid var(--border-subtle); flex-shrink: 0; background: rgba(255,255,255,0.5); }
.input-hint { font-size: 12px; color: var(--vermillion); text-align: center; margin-bottom: 8px; letter-spacing: 0.04em; }
.input-row { display: flex; gap: 10px; align-items: flex-end; }
.chat-input { flex: 1; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 11px 16px; font-size: 15px; font-family: var(--font-body); color: var(--ink-black); background: #fff; outline: none; resize: none; line-height: 1.6; max-height: 160px; transition: border-color 0.2s, box-shadow 0.2s; }
.chat-input:focus { border-color: var(--ink-black); box-shadow: 0 0 0 3px rgba(0,0,0,0.04); }
.chat-input:disabled { opacity: 0.5; background: #f9f9f9; }
.send-btn { width: 42px; height: 42px; border-radius: 8px; border: none; background: var(--ink-black); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s, transform 0.15s; flex-shrink: 0; }
.send-btn:hover:not(:disabled) { background: var(--vermillion); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.input-toolbar { display: flex; align-items: center; justify-content: flex-start; margin-top: 10px; }
.intent-badge { font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 3px; letter-spacing: 0.04em; }
.intent-badge.chat { background: #f5f5f5; color: #999; }
.intent-badge.rag { background: #e8f3eb; color: #217346; }
.mini-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 640px) { .msg-row { max-width: 92%; } }
</style>
