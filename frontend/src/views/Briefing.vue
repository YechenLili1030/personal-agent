<template>
  <div class="briefing-page">
    <!-- Top bar -->
    <div class="top-bar">
      <div class="top-left">
        <h1 class="page-title">每日简报</h1>
        <span class="date-tag" v-if="briefing">生成于 {{ briefing.created_at?.slice(0, 16) }}</span>
      </div>
      <div class="top-actions">
        <input
          type="date"
          class="date-input"
          v-model="selectedDate"
          :max="today"
        />
        <button
          class="btn btn-primary"
          :disabled="generating || !keywords.length"
          @click="handleGenerate"
        >
          <svg v-if="generating" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
          {{ generating ? '生成中…' : '生成简报' }}
        </button>
        <button class="btn btn-ghost" @click="showKeywords = !showKeywords">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          关键词设置
        </button>
      </div>
    </div>

    <!-- Keywords panel -->
    <div class="keywords-panel" v-if="showKeywords">
      <div class="keywords-header">
        <span class="keywords-label">我的兴趣关键词</span>
        <span class="keywords-hint">回车添加，点击标签删除</span>
      </div>
      <div class="keywords-input-row">
        <div class="tags-list">
          <span
            v-for="(kw, i) in keywords"
            :key="i"
            class="tag"
            @click="removeKeyword(i)"
          >{{ kw }} <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>
          <input
            class="tag-input"
            v-model="keywordInput"
            placeholder="输入关键词，回车添加"
            @keydown.enter.prevent="addKeyword"
            @keydown.backspace="handleBackspace"
          />
        </div>
        <button class="btn btn-sm" @click="saveKeywords" :disabled="savingKeywords">
          {{ savingKeywords ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="briefing-body">
      <!-- Loading skeleton -->
      <div class="skeleton-list" v-if="generating">
        <div class="skeleton-card" v-for="i in 3" :key="i">
          <div class="skeleton-line w-60"></div>
          <div class="skeleton-line w-90"></div>
          <div class="skeleton-line w-40"></div>
        </div>
      </div>

      <!-- Empty state -->
      <div class="empty-state" v-else-if="!briefing || !briefing.news_items?.length">
        <div class="empty-icon">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.4">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
        </div>
        <p class="empty-title">{{ keywords.length ? '暂无简报' : '请先设置关键词' }}</p>
        <p class="empty-desc">
          {{ keywords.length ? '选择日期后点击"生成简报"获取今日新闻摘要' : '点击右上角"关键词设置"添加感兴趣的新闻主题' }}
        </p>
      </div>

      <!-- Error state -->
      <div class="error-state" v-else-if="briefing.status === 'failed'">
        <p class="error-title">简报生成失败</p>
        <p class="error-msg">{{ briefing.error_msg }}</p>
        <button class="btn btn-primary" @click="handleGenerate">重试</button>
      </div>

      <!-- Briefing cards -->
      <template v-else>
        <h2 class="briefing-title">{{ briefing.title || `${briefing.date} 每日新闻简报` }}</h2>
        <div class="keywords-used" v-if="briefing.keywords_used?.length">
          <span class="kw-badge" v-for="kw in briefing.keywords_used" :key="kw">{{ kw }}</span>
        </div>

        <div class="news-list">
          <article
            class="news-card"
            v-for="(item, idx) in briefing.news_items"
            :key="idx"
            @click="openSource(item.source_url)"
          >
            <div class="card-index">{{ idx + 1 }}</div>
            <div class="card-body">
              <h3 class="card-title">{{ item.title }}</h3>
              <p class="card-summary">{{ item.summary }}</p>
              <div class="card-footer">
                <div class="card-tags">
                  <span class="c-tag" v-for="t in item.tags" :key="t">{{ t }}</span>
                </div>
                <span class="card-source" v-if="item.source_name">{{ item.source_name }}</span>
              </div>
            </div>
          </article>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import {
  getNewsKeywords, updateNewsKeywords,
  getBriefingList, getBriefingByDate, generateBriefing,
} from '../api/index.js'

const today = computed(() => new Date().toISOString().slice(0, 10))

const keywords = ref([])
const keywordInput = ref('')
const showKeywords = ref(false)
const savingKeywords = ref(false)

const selectedDate = ref(today.value)
const generating = ref(false)
const briefing = ref(null)
const datesWithBriefing = ref([])

onMounted(async () => {
  await loadKeywords()
  await loadDates()
  if (datesWithBriefing.value.length) {
    selectedDate.value = datesWithBriefing.value[0]
    await loadBriefing(selectedDate.value)
  }
})

watch(selectedDate, async (d) => {
  if (d) await loadBriefing(d)
})

async function loadKeywords() {
  try {
    const res = await getNewsKeywords()
    if (res.code === 0) keywords.value = res.data.keywords || []
  } catch (e) { console.error(e) }
}

async function saveKeywords() {
  savingKeywords.value = true
  try {
    await updateNewsKeywords(keywords.value)
  } catch (e) { console.error(e) }
  finally { savingKeywords.value = false }
}

function addKeyword() {
  const v = keywordInput.value.trim()
  if (v && !keywords.value.includes(v)) {
    keywords.value.push(v)
  }
  keywordInput.value = ''
}

function removeKeyword(i) {
  keywords.value.splice(i, 1)
}

function handleBackspace() {
  if (!keywordInput.value && keywords.value.length) {
    keywords.value.pop()
  }
}

async function loadDates() {
  try {
    const res = await getBriefingList()
    if (res.code === 0) {
      datesWithBriefing.value = res.data.items.map(i => i.date)
    }
  } catch (e) { console.error(e) }
}

async function loadBriefing(date) {
  try {
    const res = await getBriefingByDate(date)
    if (res.code === 0) briefing.value = res.data
    else briefing.value = null
  } catch (e) {
    console.error(e)
    briefing.value = null
  }
}

async function handleGenerate() {
  if (!keywords.value.length || generating.value) return
  generating.value = true
  briefing.value = null
  try {
    const res = await generateBriefing(selectedDate.value)
    if (res.code === 0) {
      briefing.value = res.data
      await loadDates()
    }
  } catch (e) {
    console.error(e)
  } finally {
    generating.value = false
  }
}

function openSource(url) {
  if (url) window.open(url, '_blank')
}
</script>

<style scoped>
.briefing-page {
  display: flex; flex-direction: column; height: 100vh;
  background: var(--paper);
}

/* Top bar */
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 28px; border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.top-left { display: flex; align-items: baseline; gap: 14px; }
.page-title {
  font-family: var(--font-display); font-size: 20px; font-weight: 700;
  color: var(--ink-black); letter-spacing: 0.04em;
}
.date-tag { font-size: 12px; color: var(--stone); }
.top-actions { display: flex; align-items: center; gap: 10px; }

.date-input {
  padding: 8px 12px; border: 1px solid var(--border-subtle); border-radius: 6px;
  font-size: 13px; font-family: var(--font-body); color: var(--ink-black);
  background: #fff; outline: none; transition: border-color 0.2s;
}
.date-input:focus { border-color: var(--vermillion); }

.btn {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  border: none; border-radius: 6px; font-size: 13px; font-family: var(--font-body);
  cursor: pointer; transition: all 0.2s; letter-spacing: 0.03em;
}
.btn-primary {
  background: var(--vermillion); color: #fff;
}
.btn-primary:hover:not(:disabled) { background: var(--vermillion-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost {
  background: transparent; color: var(--ink-black); border: 1px solid var(--border-subtle);
}
.btn-ghost:hover { background: rgba(0,0,0,0.03); }
.btn-sm { padding: 6px 12px; font-size: 12px; background: var(--vermillion); color: #fff; }
.btn-sm:hover:not(:disabled) { background: var(--vermillion-hover); }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }

.spin { animation: spin 1.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Keywords panel */
.keywords-panel {
  padding: 16px 28px; border-bottom: 1px solid var(--border-subtle);
  background: rgba(0,0,0,0.015); flex-shrink: 0;
}
.keywords-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
}
.keywords-label { font-size: 13px; font-weight: 600; color: var(--ink-black); }
.keywords-hint { font-size: 11px; color: var(--stone); }
.keywords-input-row { display: flex; align-items: center; gap: 10px; }
.tags-list {
  flex: 1; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  padding: 6px 10px; border: 1px solid var(--border-subtle); border-radius: 6px;
  background: #fff; min-height: 36px;
}
.tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; background: var(--vermillion-glow); color: var(--vermillion);
  border-radius: 4px; font-size: 12px; cursor: pointer; transition: background 0.2s;
}
.tag:hover { background: rgba(193, 50, 39, 0.2); }
.tag-input {
  border: none; outline: none; font-size: 13px; font-family: var(--font-body);
  color: var(--ink-black); flex: 1; min-width: 120px; background: transparent;
}
.tag-input::placeholder { color: var(--stone-light); }

/* Body */
.briefing-body {
  flex: 1; overflow-y: auto; padding: 28px;
}

/* Skeleton */
.skeleton-list { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card {
  padding: 24px; border: 1px solid var(--border-subtle); border-radius: 10px;
  background: #fff;
}
.skeleton-line {
  height: 14px; border-radius: 4px; background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);
  background-size: 200% 100%; animation: shimmer 1.5s infinite; margin-bottom: 10px;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
.skeleton-line.w-40 { width: 40%; margin-bottom: 0; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* Empty */
.empty-state { text-align: center; padding: 80px 20px; }
.empty-icon { margin-bottom: 16px; color: var(--stone); }
.empty-title { font-size: 17px; font-weight: 600; color: var(--ink-black); margin-bottom: 8px; }
.empty-desc { font-size: 13px; color: var(--stone); }

/* Error */
.error-state { text-align: center; padding: 80px 20px; }
.error-title { font-size: 17px; font-weight: 600; color: var(--vermillion); margin-bottom: 8px; }
.error-msg { font-size: 13px; color: var(--stone); margin-bottom: 20px; }

/* Briefing content */
.briefing-title {
  font-family: var(--font-display); font-size: 18px; font-weight: 700;
  color: var(--ink-black); margin-bottom: 12px; letter-spacing: 0.04em;
}
.keywords-used { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
.kw-badge {
  padding: 3px 10px; background: var(--jade-light); color: var(--jade);
  border-radius: 4px; font-size: 11px; font-weight: 500;
}

/* News cards */
.news-list { display: flex; flex-direction: column; gap: 12px; }
.news-card {
  display: flex; gap: 16px; padding: 22px 24px;
  border: 1px solid var(--border-subtle); border-radius: 10px;
  background: #fff; cursor: pointer; transition: all 0.2s;
}
.news-card:hover {
  border-color: rgba(193, 50, 39, 0.15);
  box-shadow: var(--shadow-card);
}
.card-index {
  width: 28px; height: 28px; border-radius: 6px;
  background: var(--vermillion); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; font-family: var(--font-display);
  flex-shrink: 0;
}
.card-body { flex: 1; min-width: 0; }
.card-title {
  font-size: 15px; font-weight: 600; color: var(--ink-black); margin-bottom: 6px;
  line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-summary {
  font-size: 13px; color: var(--stone); line-height: 1.7; margin-bottom: 10px;
}
.card-footer { display: flex; align-items: center; justify-content: space-between; }
.card-tags { display: flex; gap: 6px; }
.c-tag {
  padding: 2px 8px; background: var(--paper-warm); border-radius: 3px;
  font-size: 11px; color: var(--ink-black); font-weight: 500;
}
.card-source { font-size: 11px; color: var(--stone-light); }
</style>
