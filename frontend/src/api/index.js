import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

// 知识库
export function uploadKnowledge(file, category = '', inspect = false) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('category', category)
  fd.append('inspect', inspect ? 'true' : 'false')
  return api.post('/knowledge/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export function getKnowledgeList(params = {}) {
  return api.get('/knowledge/list', { params })
}

export function getKnowledgeDetail(docId) {
  return api.get(`/knowledge/${docId}`)
}

export function deleteKnowledge(docId) {
  return api.delete(`/knowledge/${docId}`)
}

export function getDocChunks(docId) {
  return api.get(`/knowledge/${docId}/chunks`)
}

export function deleteChunk(chunkId) {
  return api.delete(`/knowledge/chunks/${chunkId}`)
}

export function mergeChunks(sourceChunkId, targetChunkId, selectedText = null) {
  return api.put('/knowledge/chunks/merge', {
    source_chunk_id: sourceChunkId,
    target_chunk_id: targetChunkId,
    selected_text: selectedText || null,
  })
}

export function finalizeDocument(docId) {
  return api.post(`/knowledge/${docId}/finalize`)
}

export function buildKnowledgeGraph(docId) {
  return api.post(`/knowledge/${docId}/build-graph`)
}

export function deleteKnowledgeGraph(docId) {
  return api.delete(`/knowledge/${docId}/graph`)
}

export function getKnowledgeGraph(docId) {
  return api.get(`/knowledge/${docId}/graph`)
}

// 对话
export function createSession(title = '新对话', mode = 'normal') {
  return api.post('/chat/session/create', { title, mode })
}

export function getSessionList(params = {}) {
  return api.get('/chat/session/list', { params })
}

export function deleteSession(sessionId) {
  return api.delete(`/chat/session/${sessionId}`)
}

export function getMessageHistory(sessionId, params = {}) {
  return api.get(`/chat/message/${sessionId}/history`, { params })
}

export function createChatWebSocket(sessionId) {
  const token = localStorage.getItem('token')
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.host
  return new WebSocket(`${protocol}//${host}/api/chat/ws/${sessionId}?token=${token}`)
}

// 新闻简报
export function getNewsKeywords() {
  return api.get('/news/keywords')
}

export function updateNewsKeywords(keywords) {
  return api.put('/news/keywords', { keywords })
}

export function getBriefingList() {
  return api.get('/news/briefings')
}

export function getBriefingByDate(date) {
  return api.get(`/news/briefing/${date}`)
}

export function generateBriefing(date) {
  return api.post('/news/generate', { date })
}

export default api
