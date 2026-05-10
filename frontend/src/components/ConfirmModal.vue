<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="modal-overlay" v-if="visible" @click.self="onCancel">
        <div class="modal-card">
          <div class="modal-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <h3 class="modal-title">{{ title }}</h3>
          <p class="modal-message">{{ message }}</p>
          <div class="modal-actions">
            <button class="btn-cancel" @click="onCancel" :disabled="loading">取消</button>
            <button class="btn-confirm" @click="onConfirm" :disabled="loading">
              <span v-if="loading" class="mini-spinner"></span>
              <span v-else>确认删除</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '此操作不可撤销，确认继续？' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

function onConfirm() { emit('confirm') }
function onCancel() { emit('cancel') }
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}

.modal-card {
  background: #fff;
  border-radius: 8px;
  padding: 32px 32px 24px;
  max-width: 400px; width: 100%;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0,0,0,0.12), 0 16px 64px rgba(0,0,0,0.1);
}

.modal-icon {
  width: 52px; height: 52px; border-radius: 50%;
  background: #fef0ef; color: var(--vermillion);
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 18px;
}

.modal-title {
  font-family: var(--font-display);
  font-size: 18px; font-weight: 700;
  color: var(--ink-black); margin-bottom: 8px;
}

.modal-message {
  font-size: 14px; color: var(--stone); line-height: 1.6;
  margin-bottom: 24px;
}

.modal-actions {
  display: flex; gap: 12px; justify-content: center;
}

.btn-cancel {
  padding: 10px 24px; border-radius: 4px;
  border: 1px solid var(--border-subtle);
  background: transparent; color: var(--stone);
  font-size: 14px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s;
}
.btn-cancel:hover { border-color: var(--ink-black); color: var(--ink-black); }

.btn-confirm {
  padding: 10px 24px; border-radius: 4px; border: none;
  background: var(--vermillion); color: #fff;
  font-size: 14px; font-family: var(--font-body); cursor: pointer;
  transition: all 0.2s; display: flex; align-items: center; gap: 6px;
}
.btn-confirm:hover:not(:disabled) { background: var(--vermillion-hover); }
.btn-confirm:disabled { opacity: 0.6; cursor: not-allowed; }

.mini-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* transition */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.25s;
}
.modal-enter-active .modal-card, .modal-leave-active .modal-card {
  transition: transform 0.25s;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-card { transform: scale(0.95); }
.modal-leave-to .modal-card { transform: scale(0.95); }
</style>
