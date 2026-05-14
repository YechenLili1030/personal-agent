<template>
  <Teleport to="body">
    <transition name="modal">
      <div class="modal-overlay" v-if="visible" @click.self="$emit('close')">
        <div class="graph-card">
          <div class="graph-header">
            <div>
              <h2 class="graph-title">知识图谱</h2>
              <p class="graph-file">{{ docFilename }}</p>
            </div>
            <div class="graph-header-right">
              <span class="graph-stats" v-if="!loading">
                {{ nodes.length }} 节点 · {{ edges.length }} 关系
              </span>
              <button class="icon-btn" @click="resetView" title="重置视图">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/>
                </svg>
              </button>
              <button class="close-btn" @click="$emit('close')">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="graph-body" ref="graphContainer">
            <div v-if="loading" class="loading-state">
              <div class="loading-spinner"></div>
              <p>加载图谱数据...</p>
            </div>
            <div v-else-if="nodes.length === 0" class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
                <circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>
                <line x1="12" y1="7" x2="5" y2="17"/><line x1="12" y1="7" x2="19" y2="17"/><line x1="5" y1="17" x2="19" y2="17"/>
              </svg>
              <p>该文档暂无知识图谱数据</p>
            </div>

            <!-- Node detail sidebar -->
            <transition name="slide">
              <div v-if="selectedNode" class="node-detail">
                <h3>{{ selectedNode.name }}</h3>
                <span class="detail-type" :style="{ color: selectedNode.color }">{{ selectedNode.type }}</span>
                <p class="detail-label">关联实体</p>
                <div class="detail-connections">
                  <span
                    v-for="c in selectedNode.connections"
                    :key="c.name"
                    class="connection-tag"
                    @click="focusNode(c.name)"
                  >
                    {{ c.name }}
                    <small>{{ c.relation }}</small>
                  </span>
                </div>
                <button class="detail-close" @click="selectedNode = null">×</button>
              </div>
            </transition>
          </div>

          <div class="graph-legend" v-if="nodes.length > 0 && typeColors.size">
            <span class="legend-label">图例</span>
            <span v-for="(color, type) in typeColors" :key="type" class="legend-item">
              <span class="legend-dot" :style="{ background: color }"></span>
              {{ type }}
            </span>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount, reactive } from 'vue'
import { DataSet, Network } from 'vis-network/standalone'
import { getKnowledgeGraph } from '../api/index.js'

const props = defineProps({
  visible: Boolean,
  docId: String,
  docFilename: String,
})

defineEmits(['close'])

const graphContainer = ref(null)
const nodes = ref([])
const edges = ref([])
const loading = ref(false)
const typeColors = ref(new Map())

const selectedNode = ref(null)
const nodeIndexMap = reactive({})  // node name → node data index

let network = null

const NODE_COLORS = [
  '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
  '#1abc9c', '#e67e22', '#16a085', '#d35400', '#2980b9',
]

watch(() => props.visible, async (v) => {
  if (v && props.docId) {
    selectedNode.value = null
    loading.value = true
    try {
      const res = await getKnowledgeGraph(props.docId)
      if (res.code === 0) {
        nodes.value = res.data.nodes || []
        edges.value = res.data.edges || []
        if (nodes.value.length > 0) {
          await nextTick()
          renderGraph()
        }
      }
    } catch (e) {
      console.error('加载图谱失败', e)
      nodes.value = []
      edges.value = []
    } finally {
      loading.value = false
    }
  }
})

function renderGraph() {
  if (!graphContainer.value) return

  // Assign colors to entity types
  const colorMap = new Map()
  let colorIdx = 0
  nodes.value.forEach(n => {
    const t = n.type || '概念'
    if (!colorMap.has(t)) {
      colorMap.set(t, NODE_COLORS[colorIdx % NODE_COLORS.length])
      colorIdx++
    }
  })
  typeColors.value = colorMap

  // Build node name → index lookup
  Object.keys(nodeIndexMap).forEach(k => delete nodeIndexMap[k])
  nodes.value.forEach((n, i) => { nodeIndexMap[n.name] = i })

  // Calculate node degrees for sizing
  const degree = {}
  nodes.value.forEach((_, i) => { degree[i] = 0 })
  edges.value.forEach(e => {
    const si = nodeIndexMap[e.source]
    const ti = nodeIndexMap[e.target]
    if (si !== undefined) degree[si]++
    if (ti !== undefined) degree[ti]++
  })
  const maxDegree = Math.max(1, ...Object.values(degree))

  const nodeItems = new DataSet(
    nodes.value.map((n, i) => {
      const d = degree[i] || 0
      const size = 8 + Math.round((d / maxDegree) * 22)
      const short = n.name.length > 6 ? n.name.slice(0, 6) + '…' : n.name
      return {
        id: i,
        label: short,
        title: n.name,
        shape: 'circle',
        value: d,
        color: {
          background: colorMap.get(n.type || '概念'),
          border: '#fff',
          highlight: { background: colorMap.get(n.type || '概念'), border: '#333' },
        },
        font: { size: Math.min(13, 10 + size / 7), face: 'Inter, system-ui, sans-serif', color: '#444' },
        borderWidth: d > 1 ? 3 : 1,
        size,
      }
    })
  )

  const edgeItems = new DataSet(
    edges.value
      .filter(e => nodeIndexMap[e.source] !== undefined && nodeIndexMap[e.target] !== undefined)
      .map(e => ({
        from: nodeIndexMap[e.source],
        to: nodeIndexMap[e.target],
        label: e.relation,
        arrows: 'to',
        font: { size: 10, face: 'Inter, system-ui, sans-serif', color: '#999', strokeWidth: 2.5, align: 'middle' },
        color: { color: '#c8d6e5', opacity: 0.7, highlight: '#576574' },
        smooth: { type: 'continuous', roundness: 0.3 },
        width: 1.5,
        hoverWidth: 0,
      }))
  )

  if (network) {
    network.destroy()
  }

  network = new Network(graphContainer.value, { nodes: nodeItems, edges: edgeItems }, {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -60,
        centralGravity: 0.01,
        springLength: 180,
        springConstant: 0.05,
        damping: 0.4,
      },
      stabilization: { iterations: 150, updateInterval: 10 },
    },
    interaction: {
      zoomView: true,
      dragView: true,
      dragNodes: true,
      hover: true,
      tooltipDelay: 200,
      navigationButtons: true,
    },
    edges: { smooth: true },
    layout: { improvedLayout: true },
  })

  // Click → show node detail
  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const n = nodes.value[nodeId]
      if (n) {
        const connections = []
        edges.value.forEach(e => {
          if (e.source === n.name) connections.push({ name: e.target, relation: e.relation })
          if (e.target === n.name) connections.push({ name: e.source, relation: '← ' + e.relation })
        })
        selectedNode.value = {
          name: n.name,
          type: n.type || '概念',
          color: colorMap.get(n.type || '概念'),
          connections,
        }
      }
    } else {
      selectedNode.value = null
    }
  })
}

function resetView() {
  if (network) {
    network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } })
  }
}

function focusNode(name) {
  const idx = nodeIndexMap[name]
  if (idx !== undefined && network) {
    network.focus(idx, { scale: 1.5, animation: { duration: 400, easingFunction: 'easeInOutQuad' } })
    network.selectNodes([idx])
    // trigger click to show detail
    network.emit('click', { nodes: [idx], edges: [] })
    selectedNode.value = null  // will be set by click handler
    setTimeout(() => {
      const n = nodes.value[idx]
      if (n) {
        const connections = []
        edges.value.forEach(e => {
          if (e.source === n.name) connections.push({ name: e.target, relation: e.relation })
          if (e.target === n.name) connections.push({ name: e.source, relation: '← ' + e.relation })
        })
        selectedNode.value = {
          name: n.name,
          type: n.type || '概念',
          color: typeColors.value.get(n.type || '概念'),
          connections,
        }
      }
    }, 0)
  }
}

onBeforeUnmount(() => {
  if (network) {
    network.destroy()
    network = null
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(3px);
}
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .graph-card { animation: modal-in 0.25s ease; }
@keyframes modal-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.graph-card {
  background: #fff; border-radius: 10px;
  width: 95vw; max-width: 1100px; height: 90vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 80px rgba(0,0,0,0.2);
}

.graph-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 20px 24px 14px; border-bottom: 1px solid rgba(0,0,0,0.06);
  flex-shrink: 0;
}
.graph-header-right { display: flex; align-items: center; gap: 8px; }
.graph-title { font-size: 18px; font-weight: 700; color: #1a1a1a; margin-bottom: 2px; }
.graph-file { font-size: 13px; color: #999; }
.graph-stats { font-size: 12px; color: #999; white-space: nowrap; }

.icon-btn {
  background: none; border: 1px solid rgba(0,0,0,0.1); border-radius: 4px;
  color: #999; cursor: pointer; padding: 4px 6px;
  transition: all 0.2s;
}
.icon-btn:hover { color: #333; border-color: #333; }

.close-btn {
  background: none; border: none; color: #999; cursor: pointer;
  padding: 2px; border-radius: 3px; transition: color 0.2s;
}
.close-btn:hover { color: #333; }

.graph-body {
  flex: 1; min-height: 0;
  position: relative; overflow: hidden;
}
.loading-state, .empty-state {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #999; font-size: 14px; gap: 10px;
}
.loading-spinner {
  width: 28px; height: 28px;
  border: 3px solid rgba(0,0,0,0.1);
  border-top-color: #217346;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Node detail sidebar */
.node-detail {
  position: absolute; top: 12px; right: 12px;
  width: 220px; max-height: calc(100% - 24px);
  background: #fff; border-radius: 6px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
  padding: 16px; overflow-y: auto;
  z-index: 10;
}
.slide-enter-active, .slide-leave-active { transition: all 0.25s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateX(12px); }

.node-detail h3 {
  font-size: 15px; font-weight: 700; color: #1a1a1a; margin-bottom: 4px;
  word-break: break-all;
}
.detail-type { font-size: 12px; font-weight: 600; }
.detail-label { font-size: 11px; color: #999; margin: 12px 0 6px; text-transform: uppercase; letter-spacing: 0.04em; }
.detail-connections { display: flex; flex-wrap: wrap; gap: 6px; }
.connection-tag {
  font-size: 11px; padding: 3px 8px; border-radius: 3px;
  background: #f5f5f5; color: #555; cursor: pointer;
  transition: background 0.15s;
}
.connection-tag:hover { background: #e8e8e8; }
.connection-tag small { color: #aaa; margin-left: 3px; }
.detail-close {
  position: absolute; top: 8px; right: 10px;
  background: none; border: none; font-size: 16px; color: #ccc; cursor: pointer;
}
.detail-close:hover { color: #666; }

.graph-legend {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  padding: 10px 24px 14px; border-top: 1px solid rgba(0,0,0,0.06);
  flex-shrink: 0;
}
.legend-label { font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 4px; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #666; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
</style>
