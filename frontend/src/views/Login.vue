<template>
  <div class="login-page">
    <!-- Paper grain overlay -->
    <div class="grain-overlay"></div>

    <!-- Left: Brand / Poetic -->
    <section class="brand-panel" aria-label="品牌标识">
      <div class="brand-content">
        <!-- Seal / Chop mark -->
        <div class="chop-mark" aria-hidden="true">
          <svg viewBox="0 0 64 64" fill="none" class="chop-svg">
            <rect x="2" y="2" width="60" height="60" rx="2" stroke="currentColor" stroke-width="3"/>
            <rect x="7" y="7" width="50" height="50" rx="1" stroke="currentColor" stroke-width="1" opacity="0.5"/>
            <text x="32" y="36" text-anchor="middle" fill="currentColor" font-size="20" font-weight="900" font-family="var(--font-display)">智</text>
            <text x="32" y="54" text-anchor="middle" fill="currentColor" font-size="9" font-weight="600" letter-spacing="4">AGENT</text>
            <path d="M14 44h36" stroke="currentColor" stroke-width="0.8" opacity="0.3"/>
          </svg>
        </div>

        <h1 class="brand-name">Personal<br/>Agent</h1>

        <blockquote class="brand-verse">
          <p>博观而约取</p>
          <p>厚积而薄发</p>
          <cite>— 苏轼《稼说》</cite>
        </blockquote>

        <p class="brand-desc">你的第二大脑，让知识自然生长</p>
      </div>

      <!-- Ink wash decoration -->
      <div class="ink-wash ink-wash-1" aria-hidden="true"></div>
      <div class="ink-wash ink-wash-2" aria-hidden="true"></div>
      <div class="ink-wash ink-wash-3" aria-hidden="true"></div>
    </section>

    <!-- Right: Login form -->
    <section class="form-panel" aria-label="登录表单">
      <div class="form-content">
        <div class="form-header">
          <p class="form-eyebrow">登录</p>
          <h2>进入你的智识空间</h2>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <div class="field">
            <label for="username">用户名</label>
            <div class="input-underline">
              <input
                id="username"
                v-model="form.username"
                type="text"
                placeholder="输入用户名"
                autocomplete="username"
                :disabled="loading"
              />
              <span class="underline"></span>
            </div>
          </div>

          <div class="field">
            <label for="password">密码</label>
            <div class="input-underline">
              <input
                id="password"
                v-model="form.password"
                type="password"
                placeholder="输入密码"
                autocomplete="current-password"
                :disabled="loading"
              />
              <span class="underline"></span>
            </div>
          </div>

          <transition name="error-fade">
            <p v-if="errorMsg" class="error-msg" role="alert">{{ errorMsg }}</p>
          </transition>

          <button
            type="submit"
            class="submit-btn"
            :class="{ loading: loading }"
            :disabled="loading"
          >
            <span class="btn-text">{{ loading ? '验证中...' : '进入空间' }}</span>
            <span class="btn-arrow" aria-hidden="true">&rarr;</span>
          </button>
        </form>

        <p class="form-hint">默认账号 admin / admin123</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api/index.js'

const router = useRouter()

const form = reactive({ username: 'admin', password: 'admin123' })
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!form.username.trim() || !form.password.trim()) {
    errorMsg.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    const res = await login(form.username, form.password)
    if (res.code === 0) {
      localStorage.setItem('token', res.data.access_token)
      localStorage.setItem('user', JSON.stringify(res.data.user))
      router.push('/chat')
    } else {
      errorMsg.value = res.message || '登录失败'
    }
  } catch (err) {
    errorMsg.value = err.response?.data?.detail || '网络异常，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ============================
   Layout
   ============================ */
.login-page {
  display: flex;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

/* ============================
   Grain texture
   ============================ */
.grain-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 100;
  opacity: 0.035;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='1'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 256px 256px;
}

/* ============================
   Brand panel (left)
   ============================ */
.brand-panel {
  flex: 1;
  background: var(--ink-deep);
  color: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  min-width: 0;
}

.brand-content {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 60px 40px;
  animation: brand-reveal 0.9s ease both;
}

@keyframes brand-reveal {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Chop mark */
.chop-mark {
  color: var(--vermillion);
  width: 72px;
  margin: 0 auto 32px;
  filter: drop-shadow(0 2px 4px rgba(193,50,39,0.3));
  animation: chop-press 0.6s 0.25s cubic-bezier(0.17, 0.89, 0.32, 1.25) both;
}

@keyframes chop-press {
  from {
    opacity: 0;
    transform: scale(1.3) rotate(-3deg);
  }
  to {
    opacity: 1;
    transform: scale(1) rotate(0deg);
  }
}

.brand-name {
  font-family: var(--font-display);
  font-size: clamp(36px, 5vw, 52px);
  font-weight: 900;
  line-height: 1.2;
  letter-spacing: 0.04em;
  color: var(--paper);
  margin-bottom: 36px;
}

.brand-verse {
  font-family: var(--font-display);
  font-size: 18px;
  line-height: 1.8;
  color: var(--stone-light);
  margin-bottom: 28px;
}

.brand-verse p {
  margin: 0;
  letter-spacing: 0.15em;
}

.brand-verse cite {
  display: block;
  font-size: 13px;
  color: var(--stone);
  margin-top: 10px;
  font-style: normal;
  letter-spacing: 0.05em;
}

.brand-desc {
  font-size: 14px;
  color: var(--stone);
  letter-spacing: 0.06em;
}

/* Ink wash decorations */
.ink-wash {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.08;
  pointer-events: none;
}

.ink-wash-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, var(--vermillion), transparent 70%);
  top: -100px;
  left: -80px;
  animation: ink-drift-1 18s ease-in-out infinite;
}

.ink-wash-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, var(--gold), transparent 70%);
  bottom: -60px;
  right: -40px;
  animation: ink-drift-2 22s ease-in-out infinite;
}

.ink-wash-3 {
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, var(--jade), transparent 70%);
  top: 40%;
  left: 30%;
  animation: ink-drift-3 15s ease-in-out infinite;
}

@keyframes ink-drift-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.1); }
  66% { transform: translate(-15px, 25px) scale(0.95); }
}

@keyframes ink-drift-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-25px, -15px) scale(1.15); }
}

@keyframes ink-drift-3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, 15px) scale(1.05); }
  66% { transform: translate(-10px, -25px) scale(0.9); }
}

/* ============================
   Form panel (right)
   ============================ */
.form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--paper);
  position: relative;
  z-index: 1;
}

.form-content {
  width: 100%;
  max-width: 400px;
  padding: 60px 48px;
  animation: form-reveal 0.7s 0.15s ease both;
}

@keyframes form-reveal {
  from {
    opacity: 0;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.form-header {
  margin-bottom: 44px;
}

.form-eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--vermillion);
  font-weight: 600;
  margin-bottom: 8px;
}

.form-header h2 {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--ink-black);
  letter-spacing: 0.03em;
}

/* ============================
   Fields
   ============================ */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--stone);
  letter-spacing: 0.06em;
}

.input-underline {
  position: relative;
}

.input-underline input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 12px 0;
  font-size: 16px;
  font-family: var(--font-body);
  color: var(--ink-black);
  outline: none;
  transition: color 0.2s;
}

.input-underline input::placeholder {
  color: var(--stone-light);
}

.input-underline input:disabled {
  color: var(--stone-light);
  cursor: not-allowed;
}

.input-underline .underline {
  display: block;
  height: 1.5px;
  background: var(--border-subtle);
  position: relative;
}

.input-underline .underline::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 1.5px;
  background: var(--ink-black);
  transition: width 0.35s ease, left 0.35s ease;
}

.input-underline input:focus ~ .underline::after {
  width: 100%;
  left: 0;
}

/* ============================
   Error
   ============================ */
.error-msg {
  font-size: 13px;
  color: var(--vermillion);
  background: var(--vermillion-glow);
  padding: 10px 16px;
  border-radius: 4px;
  border-left: 3px solid var(--vermillion);
  line-height: 1.5;
}

.error-fade-enter-active,
.error-fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.error-fade-enter-from,
.error-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ============================
   Submit button
   ============================ */
.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
  padding: 14px 36px;
  background: var(--vermillion);
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 15px;
  font-weight: 600;
  font-family: var(--font-body);
  letter-spacing: 0.08em;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: background 0.25s, transform 0.15s, box-shadow 0.25s;
  align-self: flex-start;
}

.submit-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, rgba(255,255,255,0.15) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s;
}

.submit-btn:hover:not(:disabled) {
  background: var(--vermillion-hover);
  box-shadow: 0 4px 20px var(--vermillion-glow);
  transform: translateY(-1px);
}

.submit-btn:hover:not(:disabled)::before {
  opacity: 1;
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.submit-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.submit-btn.loading .btn-arrow {
  display: none;
}

.btn-arrow {
  font-size: 18px;
  transition: transform 0.25s;
}

.submit-btn:hover:not(:disabled) .btn-arrow {
  transform: translateX(4px);
}

/* ============================
   Hint
   ============================ */
.form-hint {
  margin-top: 32px;
  font-size: 12px;
  color: var(--stone-light);
  letter-spacing: 0.04em;
}

/* ============================
   Responsive
   ============================ */
@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .brand-panel {
    flex: 0 0 auto;
    padding: 48px 24px 32px;
  }

  .brand-content {
    padding: 0;
  }

  .brand-name {
    font-size: 28px;
    margin-bottom: 20px;
  }

  .brand-verse {
    font-size: 15px;
    margin-bottom: 16px;
  }

  .chop-mark {
    width: 52px;
    margin-bottom: 20px;
  }

  .form-panel {
    flex: 1;
  }

  .form-content {
    padding: 32px 28px 48px;
  }

  .form-header h2 {
    font-size: 22px;
  }
}
</style>
