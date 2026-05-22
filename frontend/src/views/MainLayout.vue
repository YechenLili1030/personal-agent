<template>
  <div class="app-layout">
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
        <router-link to="/chat" class="nav-item" :class="{ active: $route.path === '/chat' }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          对话
        </router-link>
        <router-link to="/knowledge" class="nav-item" :class="{ active: $route.path === '/knowledge' }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          知识库
        </router-link>
        <router-link to="/briefing" class="nav-item" :class="{ active: $route.path === '/briefing' }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          每日简报
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
            :class="{ current: s.session_id === activeSessionId }"
            @click="switchToChat(s.session_id)"
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

    <main class="main-area">
      <router-view />
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { createSession, getSessionList, deleteSession } from '../api/index.js'
import ConfirmModal from '../components/ConfirmModal.vue'

const router = useRouter()

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
})
const userInitial = computed(() => (user.value?.nickname || user.value?.username || '?')[0])

const sessions = ref([])
const loadingSessions = ref(false)
const activeSessionId = ref(null)

// Delete
const showDeleteModal = ref(false)
const deletingSessionId = ref(null)
const deletingLoading = ref(false)

onMounted(() => fetchSessions())

async function fetchSessions() {
  loadingSessions.value = true
  try {
    const res = await getSessionList()
    if (res.code === 0) sessions.value = res.data.items
  } catch (e) { console.error(e) }
  finally { loadingSessions.value = false }
}

async function handleNewChat() {
  try {
    const res = await createSession('新对话', 'rag')
    if (res.code === 0) {
      await fetchSessions()
      activeSessionId.value = res.data.session_id
      router.push({ path: '/chat', query: { sid: res.data.session_id } })
    }
  } catch (e) { console.error(e) }
}

function switchToChat(sid) {
  activeSessionId.value = sid
  router.push({ path: '/chat', query: { sid } })
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
    if (activeSessionId.value === sid) activeSessionId.value = null
    await fetchSessions()
  } catch (e) { console.error(e) }
  finally {
    deletingLoading.value = false
    showDeleteModal.value = false
    deletingSessionId.value = null
  }
}

function handleLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.app-layout { display: flex; height: 100vh; background: var(--paper); }

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

.main-area { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }

@media (max-width: 640px) {
  .sidebar { width: 64px; }
  .sidebar-title, .user-name, .nav-item span, .new-chat-btn span,
  .session-title, .session-mode, .session-delete, .empty-hint { display: none; }
  .nav-item, .new-chat-btn { justify-content: center; padding: 10px; }
  .sidebar-header { justify-content: center; }
}
</style>
