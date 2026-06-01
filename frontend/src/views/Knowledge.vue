<template>
  <div class="knowledge-content">
        <!-- Header -->
        <header class="page-header">
          <div>
            <h1>知识库</h1>
            <p class="header-sub">管理你的文档，构建第二大脑</p>
          </div>
          <div class="header-actions">
            <button class="refresh-btn" @click="fetchList" :disabled="loading">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: loading }">
                <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
              刷新
            </button>
          </div>
        </header>

        <!-- Upload zone -->
        <div
          class="upload-zone"
          :class="{ dragOver: dragOver, uploading: uploading }"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="handleDrop"
          @click="triggerUpload"
        >
          <input
            ref="fileInput"
            type="file"
            class="file-input-hidden"
            accept=".pdf,.docx,.xlsx,.xls,.txt,.md,.markdown,.png,.jpg,.jpeg,.bmp,.gif"
            @change="handleFileSelect"
          />
          <div class="upload-icon">
            <svg v-if="!uploading" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <div v-else class="upload-spinner"></div>
          </div>
          <p class="upload-text" v-if="!uploading">拖拽文件到此处，或 <span class="upload-link">点击上传</span></p>
          <p class="upload-text" v-else>正在上传...</p>
          <p class="upload-hint">支持 PDF / Word / Excel / TXT / Markdown / 图片 (最大 50MB)</p>
          <label class="inspect-toggle" @click.stop>
            <input type="checkbox" v-model="inspectEnabled" :disabled="uploading" />
            <span class="inspect-label">上传后检查分块</span>
            <span class="inspect-hint">分块后暂停，可手动合并相邻分块以修复语义截断</span>
          </label>
          <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>
        </div>

        <!-- Filters -->
        <div class="filters">
          <select v-model="filterType" @change="fetchList" class="filter-select">
            <option value="">全部类型</option>
            <option value="pdf">PDF</option>
            <option value="docx">Word</option>
            <option value="xlsx">Excel</option>
            <option value="txt">TXT</option>
            <option value="md">Markdown</option>
            <option value="image">图片</option>
          </select>
          <select v-model="filterStatus" @change="fetchList" class="filter-select">
            <option value="">全部状态</option>
            <option value="uploading">上传中</option>
            <option value="parsing">解析中</option>
            <option value="chunking">分块中</option>
            <option value="inspecting">待审查</option>
            <option value="embedding">向量化中</option>
            <option value="done">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>

        <!-- Doc list -->
        <div class="doc-list" v-if="docs.length > 0">
          <div class="doc-card" v-for="doc in docs" :key="doc.doc_id">
            <div class="doc-icon" :class="doc.file_type">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <div class="doc-body">
              <div class="doc-title">{{ doc.filename }}</div>
              <div class="doc-meta">
                <span>{{ doc.file_type.toUpperCase() }}</span>
                <span>{{ formatSize(doc.file_size) }}</span>
                <span v-if="doc.chunk_count">{{ doc.chunk_count }} chunks</span>
                <span v-if="doc.char_count">{{ doc.char_count }} 字</span>
                <span>{{ formatDate(doc.created_at) }}</span>
              </div>
              <div v-if="doc.status === 'failed' && doc.error_msg" class="doc-error">{{ doc.error_msg }}</div>
            </div>
            <div class="doc-actions">
              <span class="status-badge" :class="doc.status">{{ statusLabel(doc.status) }}</span>
              <span v-if="graphEnabled && doc.graph_status === 'built'" class="graph-badge built" title="知识图谱已构建">图谱</span>
              <span v-else-if="graphEnabled && doc.graph_status === 'building'" class="graph-badge building" title="知识图谱构建中">图谱构建中...</span>
              <span v-else-if="graphEnabled && doc.graph_status === 'failed'" class="graph-badge failed" title="知识图谱构建失败">图谱失败</span>

              <button
                v-if="doc.status === 'inspecting'"
                class="inspect-btn"
                @click="openInspector(doc)"
              >
                审查分块
              </button>
              <button
                v-if="doc.status === 'done' || doc.status === 'inspecting' || doc.status === 'failed'"
                class="view-btn"
                @click="openChunkViewer(doc)"
              >
                查看分块
              </button>
              <button
                v-if="graphEnabled && doc.graph_status === 'built'"
                class="view-graph-btn"
                @click="openGraphViewer(doc)"
              >
                查看图谱
              </button>
              <button
                v-if="graphEnabled && doc.status === 'done' && doc.graph_status !== 'building' && doc.graph_status !== 'built'"
                class="graph-build-btn"
                :disabled="graphBuilding[doc.doc_id]"
                @click="handleBuildGraph(doc)"
              >
                {{ graphBuilding[doc.doc_id] ? '构建中...' : '构建图谱' }}
              </button>
              <button
                v-if="graphEnabled && doc.graph_status === 'built'"
                class="graph-del-btn"
                @click="handleDeleteGraph(doc)"
                title="删除知识图谱"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/>
                </svg>
              </button>
              <button class="delete-btn" @click="handleDelete(doc)" title="删除文档">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Empty -->
        <div class="empty-state" v-else-if="!loading">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <p class="empty-title">知识库为空</p>
          <p class="empty-hint">上传你的第一份文档开始构建知识库</p>
        </div>

        <!-- Pagination -->
        <div class="pagination" v-if="totalPages > 1">
          <button :disabled="page <= 1" @click="goPage(page - 1)">&larr;</button>
          <span class="page-info">{{ page }} / {{ totalPages }}</span>
          <button :disabled="page >= totalPages" @click="goPage(page + 1)">&rarr;</button>
        </div>
  </div>

  <ConfirmModal
    :visible="showDeleteModal"
    title="删除文档"
    :message="`确认删除「${deletingDoc?.filename || ''}」？相关的分块和向量数据将被清除，此操作不可撤销。`"
    :loading="deletingLoading"
    @confirm="confirmDelete"
    @cancel="showDeleteModal = false"
  />

  <ChunkInspectorModal
    :visible="showInspector"
    :docId="inspectingDoc?.doc_id || ''"
    :docFilename="inspectingDoc?.filename || ''"
    @close="showInspector = false"
    @finalized="onInspectorFinalized"
  />

  <ChunkViewerModal
    :visible="showChunkViewer"
    :docId="viewingDoc?.doc_id || ''"
    :docFilename="viewingDoc?.filename || ''"
    @close="showChunkViewer = false"
  />

  <GraphViewerModal
    :visible="showGraphViewer"
    :docId="viewingGraphDoc?.doc_id || ''"
    :docFilename="viewingGraphDoc?.filename || ''"
    @close="showGraphViewer = false"
  />
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import ChunkInspectorModal from '../components/ChunkInspectorModal.vue'
import ChunkViewerModal from '../components/ChunkViewerModal.vue'
import GraphViewerModal from '../components/GraphViewerModal.vue'
import { getKnowledgeList, uploadKnowledge, deleteKnowledge, buildKnowledgeGraph, deleteKnowledgeGraph } from '../api/index.js'

const graphEnabled = false

const fileInput = ref(null)

// Upload
const dragOver = ref(false)
const uploading = ref(false)
const uploadError = ref('')
const inspectEnabled = ref(false)

// List
const docs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filterType = ref('')
const filterStatus = ref('')
const loading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filterType.value) params.file_type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getKnowledgeList(params)
    if (res.code === 0) {
      docs.value = res.data.items
      total.value = res.data.total
    }
  } catch (e) {
    console.error('加载失败', e)
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  page.value = p
  fetchList()
}

// Upload
function triggerUpload() {
  if (uploading.value) return
  fileInput.value?.click()
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) doUpload(file)
  e.target.value = ''
}

function handleDrop(e) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) doUpload(file)
}

async function doUpload(file) {
  uploadError.value = ''
  uploading.value = true
  try {
    const res = await uploadKnowledge(file, '', inspectEnabled.value)
    if (res.code === 0) {
      page.value = 1
      await fetchList()
    } else {
      uploadError.value = res.message || '上传失败'
    }
  } catch (e) {
    uploadError.value = e.response?.data?.detail || '上传失败，请重试'
  } finally {
    uploading.value = false
  }
}

// Delete
const showDeleteModal = ref(false)
const deletingDoc = ref(null)
const deletingLoading = ref(false)

function handleDelete(doc) {
  deletingDoc.value = doc
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!deletingDoc.value) return
  deletingLoading.value = true
  try {
    const res = await deleteKnowledge(deletingDoc.value.doc_id)
    if (res.code === 0) {
      await fetchList()
    }
  } catch (e) {
    console.error('删除失败', e)
  } finally {
    deletingLoading.value = false
    showDeleteModal.value = false
    deletingDoc.value = null
  }
}

// Inspector
const showInspector = ref(false)
const inspectingDoc = ref(null)

function openInspector(doc) {
  inspectingDoc.value = doc
  showInspector.value = true
}

function onInspectorFinalized() {
  fetchList()
}

// Chunk viewer (read-only)
const showChunkViewer = ref(false)
const viewingDoc = ref(null)

function openChunkViewer(doc) {
  viewingDoc.value = doc
  showChunkViewer.value = true
}

// Graph viewer
const showGraphViewer = ref(false)
const viewingGraphDoc = ref(null)

function openGraphViewer(doc) {
  viewingGraphDoc.value = doc
  showGraphViewer.value = true
}

// Graph
const graphBuilding = ref({})

async function handleBuildGraph(doc) {
  graphBuilding.value = { ...graphBuilding.value, [doc.doc_id]: true }
  try {
    const res = await buildKnowledgeGraph(doc.doc_id)
    if (res.code === 0) {
      doc.graph_status = 'building'
      // 轮询或延迟刷新以获取最终状态
      setTimeout(() => fetchList(), 3000)
      setTimeout(() => fetchList(), 8000)
    }
  } catch (e) {
    console.error('图谱构建失败', e)
  } finally {
    graphBuilding.value = { ...graphBuilding.value, [doc.doc_id]: false }
  }
}

async function handleDeleteGraph(doc) {
  try {
    const res = await deleteKnowledgeGraph(doc.doc_id)
    if (res.code === 0) {
      doc.graph_status = null
    }
  } catch (e) {
    console.error('图谱删除失败', e)
  }
}

// Format helpers
function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function statusLabel(s) {
  const map = { uploading: '上传中', parsing: '解析中', chunking: '分块中', inspecting: '待审查', embedding: '向量化', done: '已完成', failed: '失败' }
  return map[s] || s
}

</script>

<style scoped>
.knowledge-content {
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: 40px 36px 60px;
  overflow-y: auto;
  height: 100%;
}

/* Header */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}

.page-header h1 {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink-black);
  margin-bottom: 4px;
}

.header-sub {
  font-size: 14px;
  color: var(--stone);
}

.refresh-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  font-size: 13px; font-family: var(--font-body);
  color: var(--stone);
  cursor: pointer;
  transition: all 0.2s;
}
.refresh-btn:hover { border-color: var(--ink-black); color: var(--ink-black); }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Upload zone */
.upload-zone {
  border: 2px dashed rgba(0,0,0,0.1);
  border-radius: 6px;
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s;
  margin-bottom: 24px;
  position: relative;
}
.upload-zone:hover,
.upload-zone.dragOver {
  border-color: var(--vermillion);
  background: var(--vermillion-glow);
}

.upload-zone.uploading {
  pointer-events: none;
  opacity: 0.7;
}

.file-input-hidden { display: none; }

.upload-icon { margin-bottom: 12px; color: var(--stone); }

.upload-spinner {
  width: 28px; height: 28px;
  border: 3px solid rgba(0,0,0,0.1);
  border-top-color: var(--vermillion);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}

.upload-text { font-size: 15px; color: var(--ink-black); margin-bottom: 6px; }
.upload-link { color: var(--vermillion); text-decoration: underline; text-underline-offset: 2px; }
.upload-hint { font-size: 12px; color: var(--stone-light); }
.upload-error { font-size: 13px; color: var(--vermillion); margin-top: 8px; }

/* Filters */
.filters {
  display: flex; gap: 10px; margin-bottom: 20px;
}

.filter-select {
  padding: 8px 14px;
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  background: #fff;
  font-size: 13px; font-family: var(--font-body);
  color: var(--ink-black);
  outline: none;
  cursor: pointer;
}
.filter-select:focus { border-color: var(--ink-black); }

/* Doc list */
.doc-list {
  display: flex; flex-direction: column; gap: 6px;
}

.doc-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.doc-card:hover {
  border-color: rgba(0,0,0,0.12);
  box-shadow: var(--shadow-card);
}

.doc-icon {
  width: 40px; height: 40px;
  border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  color: var(--stone);
  background: rgba(0,0,0,0.03);
}
.doc-icon.pdf { color: #c13227; background: #fef0ef; }
.doc-icon.docx { color: #2b5797; background: #eef2f8; }
.doc-icon.xlsx { color: #217346; background: #e8f3eb; }
.doc-icon.md { color: #3d5648; background: #e8efe9; }
.doc-icon.txt { color: var(--stone); background: #f5f5f5; }
.doc-icon.image { color: #b8944b; background: #faf7f0; }

.doc-body { flex: 1; min-width: 0; }

.doc-title {
  font-size: 14px; font-weight: 600; color: var(--ink-black);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 4px;
}

.doc-meta {
  display: flex; gap: 12px; flex-wrap: wrap;
  font-size: 12px; color: var(--stone-light);
}
.doc-meta span { white-space: nowrap; }

.doc-error {
  font-size: 12px; color: var(--vermillion);
  margin-top: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.doc-actions {
  display: flex; align-items: center; gap: 10px;
  flex-shrink: 0;
}

.status-badge {
  font-size: 11px; font-weight: 600;
  padding: 4px 10px; border-radius: 3px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.status-badge.uploading,
.status-badge.parsing,
.status-badge.chunking,
.status-badge.embedding { background: #fdf6e3; color: #b8944b; }
.status-badge.done { background: #e8efe9; color: #3d5648; }
.status-badge.failed { background: #fef0ef; color: #c13227; }
.status-badge.inspecting { background: #eef2f8; color: #2b5797; }

.inspect-btn {
  padding: 5px 14px; border-radius: 3px;
  border: 1px solid #2b5797;
  background: transparent; color: #2b5797;
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.inspect-btn:hover { background: #f0f4fa; }

.graph-badge {
  font-size: 11px; font-weight: 600;
  padding: 4px 10px; border-radius: 3px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.graph-badge.built { background: #e8f3eb; color: #217346; }
.graph-badge.building { background: #fdf6e3; color: #b8944b; animation: pulse-graph 1.5s ease-in-out infinite; }
.graph-badge.failed { background: #fef0ef; color: #c13227; }

@keyframes pulse-graph {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.graph-build-btn {
  padding: 5px 14px; border-radius: 3px;
  border: 1px solid #217346;
  background: transparent; color: #217346;
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.graph-build-btn:hover:not(:disabled) { background: #e8f3eb; }
.graph-build-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.graph-del-btn {
  background: none; border: none;
  color: var(--stone-light); cursor: pointer;
  padding: 2px; border-radius: 3px;
  transition: color 0.2s;
}
.graph-del-btn:hover { color: var(--vermillion); }

.view-btn {
  padding: 5px 14px; border-radius: 3px;
  border: 1px solid var(--stone-light);
  background: transparent; color: var(--stone);
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.view-btn:hover { border-color: var(--ink-black); color: var(--ink-black); }

.view-graph-btn {
  padding: 5px 14px; border-radius: 3px;
  border: 1px solid #217346;
  background: transparent; color: #217346;
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.view-graph-btn:hover { background: #e8f3eb; }

.inspect-toggle {
  display: inline-flex; align-items: center; gap: 8px;
  margin-top: 12px; cursor: pointer; font-size: 13px;
  color: var(--ink-black);
}
.inspect-toggle input[type="checkbox"] {
  accent-color: var(--vermillion);
  width: 15px; height: 15px;
}
.inspect-toggle input[type="checkbox"]:disabled { opacity: 0.4; }
.inspect-label { font-weight: 500; }
.inspect-hint { font-size: 11px; color: var(--stone-light); }

.delete-btn {
  background: none; border: none;
  color: var(--stone-light); cursor: pointer;
  padding: 4px; border-radius: 3px;
  transition: color 0.2s;
}
.delete-btn:hover { color: var(--vermillion); }

/* Empty */
.empty-state {
  text-align: center; padding: 64px 0;
  animation: welcome-in 0.7s ease both;
}
@keyframes welcome-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.empty-icon { margin-bottom: 16px; }
.empty-title { font-family: var(--font-display); font-size: 20px; color: var(--ink-black); margin-bottom: 6px; }
.empty-hint { font-size: 14px; color: var(--stone); }

/* Pagination */
.pagination {
  display: flex; align-items: center; justify-content: center; gap: 16px;
  margin-top: 28px;
}
.pagination button {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  font-size: 14px; color: var(--ink-black);
  cursor: pointer;
}
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { border-color: var(--ink-black); }
.page-info { font-size: 13px; color: var(--stone); }

@media (max-width: 640px) {
  .knowledge-content { padding: 24px 16px 40px; }
  .page-header { flex-direction: column; gap: 12px; }
  .doc-meta { gap: 8px; }
}
</style>
