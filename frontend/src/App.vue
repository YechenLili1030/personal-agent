<template>
  <div id="app-root">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
</script>

<style>
:root {
  --ink-black: #1c1c1c;
  --ink-deep: #2a2520;
  --paper: #f7f3eb;
  --paper-warm: #ede6d8;
  --vermillion: #c13227;
  --vermillion-hover: #a0291f;
  --vermillion-glow: rgba(193, 50, 39, 0.12);
  --stone: #8b8580;
  --stone-light: #b8b2ac;
  --jade: #3d5648;
  --jade-light: #e8efe9;
  --gold: #b8944b;
  --border-subtle: rgba(0,0,0,0.06);
  --font-display: 'Noto Serif SC', 'SimSun', 'STSong', serif;
  --font-body: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif;
  --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 8px 32px rgba(0,0,0,0.06);
  --shadow-elevated: 0 2px 6px rgba(0,0,0,0.05), 0 16px 48px rgba(0,0,0,0.09);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-body);
  background: var(--paper);
  color: var(--ink-black);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app-root {
  width: 100%;
  min-height: 100vh;
}

/* Page transitions */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Selection color */
::selection {
  background: var(--vermillion);
  color: #fff;
}
</style>
