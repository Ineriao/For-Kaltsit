<template>
  <div class="pet-root" @mousedown="onDragStart">
    <div class="pet-glow-border" />

    <!-- webm 动画播放层 -->
    <div class="pet-video-area" @click="handleClick">
      <video
        ref="videoEl"
        class="pet-video"
        :src="currentSrc"
        autoplay
        loop
        muted
        playsinline
        preload="auto"
      />
      <!-- 点击涟漪 -->
      <div v-if="ripple.show" class="ripple" :style="{ left: ripple.x + 'px', top: ripple.y + 'px' }" />
    </div>

    <!-- 底部栏：名字 + 展开按钮 -->
    <div class="pet-footer" @click.stop="$emit('open-chat')">
      <span class="pet-name">凯尔希</span>
      <span class="pet-expand-icon">▷</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

defineEmits(['open-chat'])

// webm 动画列表（从 backend /model 静态服务获取）
const BASE = 'http://127.0.0.1:8765/model'
const MODELS = {
  default:  `${BASE}/凯尔希·思衡托-默认-基建-Default-x1.webm`,
  interact: `${BASE}/凯尔希·思衡托-默认-基建-Interact-x1.webm`,
  relax:    `${BASE}/凯尔希·思衡托-默认-基建-Relax-x1.webm`,
  sit:      `${BASE}/凯尔希·思衡托-默认-基建-Sit-x1.webm`,
  sleep:    `${BASE}/凯尔希·思衡托-默认-基建-Sleep-x1.webm`,
}

const videoEl = ref(null)
const state = ref('default') // 当前动画状态
const ripple = ref({ show: false, x: 0, y: 0 })

const currentSrc = computed(() => MODELS[state.value] ?? MODELS.default)

// 空闲时随机切换动画
let idleTimer = null
function scheduleIdle() {
  clearTimeout(idleTimer)
  const delay = 15000 + Math.random() * 20000
  idleTimer = setTimeout(() => {
    const idle = ['relax', 'sit', 'default']
    state.value = idle[Math.floor(Math.random() * idle.length)]
    scheduleIdle()
  }, delay)
}

function handleClick(e) {
  // 播放 interact 动画，3s 后回到 default
  state.value = 'interact'
  showRipple(e)
  clearTimeout(idleTimer)
  setTimeout(() => {
    state.value = 'default'
    scheduleIdle()
  }, 3000)
}

function showRipple(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  ripple.value = { show: true, x: e.clientX - rect.left, y: e.clientY - rect.top }
  setTimeout(() => { ripple.value.show = false }, 500)
}

onMounted(() => scheduleIdle())
onUnmounted(() => clearTimeout(idleTimer))

// 无边框拖拽
let dragStart = null
function onDragStart(e) {
  if (e.target.closest('.pet-footer')) return
  dragStart = { x: e.screenX, y: e.screenY }
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragEnd)
}
function onDragMove(e) {
  if (!dragStart) return
  window.electronAPI?.dragWindow({
    deltaX: e.screenX - dragStart.x,
    deltaY: e.screenY - dragStart.y
  })
  dragStart = { x: e.screenX, y: e.screenY }
}
function onDragEnd() {
  dragStart = null
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
}
</script>

<style scoped>
.pet-root {
  width: 180px;
  height: 240px;
  background: rgba(6, 10, 16, 0.85);
  border: 1px solid var(--ak-cyan-border);
  box-shadow: 0 0 24px rgba(74, 243, 227, 0.1);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.pet-root:hover {
  box-shadow: 0 0 36px rgba(74, 243, 227, 0.22);
}

.pet-glow-border {
  position: absolute;
  inset: 0;
  border: 1px solid transparent;
  background: linear-gradient(135deg, rgba(74,243,227,0.12), transparent 50%) border-box;
  pointer-events: none;
  z-index: 1;
}

.pet-video-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.pet-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: bottom center;
}

.ripple {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(74, 243, 227, 0.25);
  transform: translate(-50%, -50%) scale(0);
  animation: rippleAnim 0.5s ease-out forwards;
  pointer-events: none;
}

@keyframes rippleAnim {
  to { transform: translate(-50%, -50%) scale(3); opacity: 0; }
}

.pet-footer {
  height: 28px;
  background: rgba(4, 8, 14, 0.95);
  border-top: 1px solid var(--ak-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}

.pet-footer:hover { background: rgba(74, 243, 227, 0.05); }

.pet-name {
  font-size: 10px;
  letter-spacing: 0.15em;
  color: var(--ak-cyan);
  font-family: monospace;
}

.pet-expand-icon {
  font-size: 9px;
  color: var(--ak-text-dim);
  transition: color 0.15s;
}

.pet-footer:hover .pet-expand-icon { color: var(--ak-cyan); }
</style>
