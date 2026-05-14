<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="modal-overlay" v-if="visible" @click.self="$emit('close')">
        <div class="viewer-card">
          <div class="viewer-header">
            <div>
              <h2 class="viewer-title">分块预览</h2>
              <p class="viewer-file">{{ docFilename }}</p>
            </div>
            <div class="viewer-header-right">
              <span class="chunk-count" v-if="!loading">{{ chunks.length }} 个分块</span>
              <button class="close-btn" @click="$emit('close')">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="viewer-body" v-if="!loading">
            <div v-if="chunks.length === 0" class="empty-state">暂无分块数据</div>

            <div
              v-for="(chunk, idx) in chunks"
              :key="chunk.chunk_id"
              class="chunk-card"
            >
              <div class="chunk-header">
                <span class="chunk-index">#{{ chunk.chunk_index + 1 }}</span>
                <span class="chunk-chars">{{ chunk.char_count }} 字符</span>
              </div>
              <pre class="chunk-content">{{ chunk.content }}</pre>
            </div>
          </div>

          <div class="viewer-body loading-state" v-else>
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getDocChunks } from '../api/index.js'

const props = defineProps({
  visible: Boolean,
  docId: String,
  docFilename: String,
})

defineEmits(['close'])

const chunks = ref([])
const loading = ref(false)

watch(() => props.visible, async (v) => {
  if (v && props.docId) {
    loading.value = true
    try {
      const res = await getDocChunks(props.docId)
      if (res.code === 0) {
        chunks.value = res.data.chunks || []
      }
    } catch (e) {
      console.error('加载分块失败', e)
    } finally {
      loading.value = false
    }
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .viewer-card { animation: modal-in 0.25s ease; }
@keyframes modal-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.viewer-card {
  background: #fff; border-radius: 8px;
  width: 90vw; max-width: 720px; max-height: 85vh;
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}

.viewer-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 24px 28px 16px; border-bottom: 1px solid rgba(0,0,0,0.06);
}
.viewer-header-right { display: flex; align-items: center; gap: 12px; }
.viewer-title { font-size: 18px; font-weight: 700; color: #1a1a1a; margin-bottom: 2px; }
.viewer-file { font-size: 13px; color: #999; }
.chunk-count { font-size: 12px; color: #999; white-space: nowrap; }

.close-btn {
  background: none; border: none; color: #999; cursor: pointer;
  padding: 2px; border-radius: 3px; transition: color 0.2s;
}
.close-btn:hover { color: #333; }

.viewer-body {
  flex: 1; overflow-y: auto; padding: 20px 28px 28px;
  display: flex; flex-direction: column; gap: 12px;
}
.loading-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 60px 0; color: #999; font-size: 14px;
}
.loading-spinner {
  width: 28px; height: 28px;
  border: 3px solid rgba(0,0,0,0.1);
  border-top-color: #c13227;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 10px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state { text-align: center; padding: 40px 0; color: #999; font-size: 14px; }

.chunk-card {
  border: 1px solid rgba(0,0,0,0.06); border-radius: 4px;
  padding: 14px 16px; transition: border-color 0.2s;
}
.chunk-card:hover { border-color: rgba(0,0,0,0.12); }
.chunk-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 8px;
}
.chunk-index { font-size: 12px; font-weight: 600; color: #b8944b; }
.chunk-chars { font-size: 11px; color: #bbb; }
.chunk-content {
  font-size: 13px; line-height: 1.7; color: #444;
  white-space: pre-wrap; word-break: break-all;
  font-family: var(--font-body);
  max-height: 300px; overflow-y: auto;
}
</style>
