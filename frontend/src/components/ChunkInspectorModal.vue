<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="modal-overlay" v-if="visible" @click.self="close">
        <div class="inspector-card">
          <div class="inspector-header">
            <div>
              <h2 class="inspector-title">分块审查</h2>
              <p class="inspector-file">{{ docFilename }}</p>
            </div>
            <span class="chunk-count">{{ chunks.length }} 个分块</span>
          </div>

          <div class="inspector-body" v-if="!loading">
            <div v-if="chunks.length === 0" class="empty-chunks">暂无分块</div>

            <div
              v-for="(chunk, idx) in chunks"
              :key="chunk.chunk_id"
              class="chunk-card"
              :class="{
                'is-source': sourceChunkId === chunk.chunk_id,
                'is-target-available': isAdjacentToSource(chunk)
              }"
            >
              <div class="chunk-header">
                <div class="chunk-header-left">
                  <span class="chunk-index">#{{ chunk.chunk_index + 1 }}</span>
                  <span class="chunk-chars">{{ chunk.char_count }} 字符</span>
                </div>
                <span v-if="sourceChunkId === chunk.chunk_id" class="source-badge">文本源</span>
              </div>

              <pre
                class="chunk-content"
                :class="{ selecting: sourceChunkId === chunk.chunk_id }"
              >{{ chunk.content }}</pre>

              <div class="chunk-actions">
                <!-- 自己是文本源: 提示选中文本 -->
                <span v-if="sourceChunkId === chunk.chunk_id" class="select-hint">
                  请在上方选中要移动的文本，然后点击目标块的"接收选中文本"
                </span>

                <!-- 相邻块: 接收选中文本 -->
                <button
                  v-if="isAdjacentToSource(chunk)"
                  class="receive-btn"
                  :disabled="merging"
                  @click="doPartialMerge(chunk)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg>
                  接收选中文本
                </button>

                <!-- 选择文本按钮（非文本源时） -->
                <button
                  v-if="sourceChunkId !== chunk.chunk_id"
                  class="select-source-btn"
                  :disabled="merging"
                  @click="setSource(chunk)"
                >
                  选择文本合并
                </button>

                <!-- 取消选择 -->
                <button
                  v-if="sourceChunkId === chunk.chunk_id"
                  class="cancel-source-btn"
                  @click="clearSource"
                >
                  取消
                </button>

                <span class="action-divider"></span>

                <button
                  class="delete-chunk-btn"
                  :disabled="merging || chunks.length <= 1"
                  @click="doDeleteChunk(chunk)"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  删除
                </button>

                <span class="action-divider"></span>

                <button
                  class="merge-btn"
                  :disabled="idx === 0 || merging"
                  @click="doFullMerge(chunk, 'prev')"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                  合并整块到上一个
                </button>
                <button
                  class="merge-btn"
                  :disabled="idx === chunks.length - 1 || merging"
                  @click="doFullMerge(chunk, 'next')"
                >
                  合并整块到下一个
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                </button>
              </div>
            </div>
          </div>

          <div class="inspector-body" v-else>
            <div class="loading-state">加载分块中...</div>
          </div>

          <div class="inspector-footer">
            <button class="btn-cancel" @click="close" :disabled="finalizing">返回</button>
            <button class="btn-finalize" @click="doFinalize" :disabled="finalizing || chunks.length === 0">
              <span v-if="finalizing" class="mini-spinner"></span>
              <span v-else>确认并向量化</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getDocChunks, deleteChunk, mergeChunks, finalizeDocument } from '../api/index.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  docId: { type: String, default: '' },
  docFilename: { type: String, default: '' },
})

const emit = defineEmits(['close', 'finalized'])

const chunks = ref([])
const loading = ref(false)
const merging = ref(false)
const finalizing = ref(false)
const sourceChunkId = ref(null)

watch(() => props.visible, (v) => {
  if (v) {
    sourceChunkId.value = null
    loadChunks()
  }
})

function getSelectedText() {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed) return ''
  return sel.toString().trim()
}

async function loadChunks() {
  if (!props.docId) return
  loading.value = true
  try {
    const res = await getDocChunks(props.docId)
    if (res.code === 0) chunks.value = res.data.chunks
  } catch (e) {
    console.error('加载分块失败', e)
  } finally {
    loading.value = false
  }
}

function setSource(chunk) {
  sourceChunkId.value = chunk.chunk_id
}

function clearSource() {
  sourceChunkId.value = null
}

function getSourceChunk() {
  return chunks.value.find(c => c.chunk_id === sourceChunkId.value)
}

async function doDeleteChunk(chunk) {
  if (!confirm(`确认删除分块 #${chunk.chunk_index + 1}？此操作不可撤销。`)) return
  merging.value = true
  try {
    const res = await deleteChunk(chunk.chunk_id)
    if (res.code === 0) {
      chunks.value = res.data.chunks
      if (sourceChunkId.value === chunk.chunk_id) sourceChunkId.value = null
    }
  } catch (e) {
    console.error('删除失败', e)
    alert(e.response?.data?.detail || '删除失败')
  } finally {
    merging.value = false
  }
}

function isAdjacentToSource(chunk) {
  if (!sourceChunkId.value || sourceChunkId.value === chunk.chunk_id) return false
  const src = getSourceChunk()
  if (!src) return false
  return Math.abs(chunk.chunk_index - src.chunk_index) === 1
}

async function doPartialMerge(targetChunk) {
  const selectedText = getSelectedText()
  if (!selectedText) {
    alert('请先在文本源中选中要移动的文本内容')
    return
  }
  if (targetChunk.chunk_id === sourceChunkId.value) {
    alert('目标分块不能与文本源相同')
    return
  }

  merging.value = true
  try {
    const res = await mergeChunks(sourceChunkId.value, targetChunk.chunk_id, selectedText)
    if (res.code === 0) {
      chunks.value = res.data.chunks
      sourceChunkId.value = null
    }
  } catch (e) {
    console.error('合并失败', e)
    alert(e.response?.data?.detail || '合并失败')
  } finally {
    merging.value = false
  }
}

async function doFullMerge(chunk, direction) {
  merging.value = true
  try {
    const sourceId = chunk.chunk_id
    const targetIdx = direction === 'prev'
      ? chunk.chunk_index - 1
      : chunk.chunk_index + 1
    const target = chunks.value.find(c => c.chunk_index === targetIdx)
    if (!target) return
    const res = await mergeChunks(sourceId, target.chunk_id)
    if (res.code === 0) {
      chunks.value = res.data.chunks
      if (sourceChunkId.value === sourceId) sourceChunkId.value = null
    }
  } catch (e) {
    console.error('合并失败', e)
    alert(e.response?.data?.detail || '合并失败')
  } finally {
    merging.value = false
  }
}

async function doFinalize() {
  finalizing.value = true
  try {
    const res = await finalizeDocument(props.docId)
    if (res.code === 0) {
      emit('finalized')
      emit('close')
    }
  } catch (e) {
    console.error('向量化失败', e)
    alert(e.response?.data?.detail || '向量化失败')
  } finally {
    finalizing.value = false
  }
}

function close() {
  if (!finalizing.value) emit('close')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}

.inspector-card {
  background: #fff;
  border-radius: 8px;
  max-width: 740px; width: 100%;
  max-height: 85vh;
  display: flex; flex-direction: column;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12), 0 16px 64px rgba(0,0,0,0.1);
}

.inspector-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--border-subtle);
}

.inspector-title {
  font-family: var(--font-display);
  font-size: 18px; font-weight: 700;
  color: var(--ink-black); margin-bottom: 4px;
}

.inspector-file {
  font-size: 13px; color: var(--stone);
}

.chunk-count {
  font-size: 12px; font-weight: 600;
  padding: 4px 10px; border-radius: 3px;
  background: #eef2f8; color: #2b5797;
  white-space: nowrap;
}

.inspector-body {
  flex: 1; overflow-y: auto;
  padding: 20px 24px;
}

.loading-state, .empty-chunks {
  text-align: center; padding: 40px 0;
  font-size: 14px; color: var(--stone);
}

/* Chunk card states */
.chunk-card {
  border: 1px solid var(--border-subtle);
  border-left: 3px solid transparent;
  border-radius: 4px; padding: 16px;
  margin-bottom: 12px;
  transition: border-color 0.2s, background 0.2s;
}

.chunk-card.is-source {
  border-left-color: #2b5797;
  background: #f6f8fc;
}

.chunk-card.is-target-available:hover {
  border-left-color: #b8944b;
  background: #fdfbf7;
}

.chunk-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}

.chunk-header-left {
  display: flex; align-items: center; gap: 10px;
}

.chunk-index {
  font-size: 12px; font-weight: 700; color: var(--ink-black);
  background: rgba(0,0,0,0.04);
  padding: 2px 8px; border-radius: 3px;
}

.chunk-chars {
  font-size: 11px; color: var(--stone-light);
}

.source-badge {
  font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 3px;
  background: #2b5797; color: #fff;
}

.chunk-content {
  font-family: var(--font-body);
  font-size: 13px; line-height: 1.7;
  color: var(--ink-black);
  white-space: pre-wrap;
  max-height: 180px; overflow-y: auto;
  padding: 10px 12px;
  background: rgba(0,0,0,0.015);
  border-radius: 3px;
  margin-bottom: 12px;
  user-select: text;
  cursor: text;
}

.chunk-content.selecting {
  background: #f0f4fa;
  border: 1px dashed #a0b4d0;
}

.chunk-actions {
  display: flex; align-items: center; gap: 6px;
  flex-wrap: wrap;
}

.select-hint {
  font-size: 11px; color: #2b5797;
  flex: 1; min-width: 0;
}

.select-source-btn {
  padding: 4px 10px; border-radius: 3px;
  border: 1px dashed #2b5797;
  background: transparent; color: #2b5797;
  font-size: 11px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.select-source-btn:hover:not(:disabled) {
  background: #f0f4fa; border-style: solid;
}
.select-source-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.cancel-source-btn {
  padding: 4px 10px; border-radius: 3px;
  border: 1px solid #c13227;
  background: transparent; color: #c13227;
  font-size: 11px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.cancel-source-btn:hover { background: #fef0ef; }

.receive-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 3px;
  border: 1px solid #b8944b;
  background: #faf7f0; color: #8b6d2b;
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.receive-btn:hover:not(:disabled) {
  background: #b8944b; color: #fff;
}
.receive-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.delete-chunk-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 3px;
  border: 1px solid var(--border-subtle);
  background: transparent; color: var(--stone-light);
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.delete-chunk-btn:hover:not(:disabled) {
  border-color: #c13227; color: #c13227; background: #fef0ef;
}
.delete-chunk-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.action-divider {
  width: 1px; height: 18px;
  background: var(--border-subtle);
  margin: 0 4px;
}

.merge-btn {
  display: flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 3px;
  border: 1px solid var(--border-subtle);
  background: transparent; color: var(--stone);
  font-size: 12px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s;
}
.merge-btn:hover:not(:disabled) {
  border-color: #2b5797; color: #2b5797; background: #f0f4fa;
}
.merge-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.inspector-footer {
  display: flex; gap: 12px; justify-content: flex-end;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-subtle);
}

.btn-cancel {
  padding: 10px 24px; border-radius: 4px;
  border: 1px solid var(--border-subtle);
  background: transparent; color: var(--stone);
  font-size: 14px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s;
}
.btn-cancel:hover:not(:disabled) { border-color: var(--ink-black); color: var(--ink-black); }
.btn-cancel:disabled { opacity: 0.5; }

.btn-finalize {
  padding: 10px 24px; border-radius: 4px; border: none;
  background: var(--vermillion); color: #fff;
  font-size: 14px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.btn-finalize:hover:not(:disabled) { background: var(--vermillion-hover); }
.btn-finalize:disabled { opacity: 0.6; cursor: not-allowed; }

.mini-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.modal-enter-active, .modal-leave-active {
  transition: opacity 0.25s;
}
.modal-enter-active .inspector-card, .modal-leave-active .inspector-card {
  transition: transform 0.25s;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .inspector-card { transform: scale(0.95); }
.modal-leave-to .inspector-card { transform: scale(0.95); }
</style>
