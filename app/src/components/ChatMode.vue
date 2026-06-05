<template>
  <div class="chat-root">

    <!-- 立绘 -->
    <div class="sprite-wrap" @mousedown="onSpriteTouch">
      <img class="sprite" :src="spriteUrl" alt="凯尔希" draggable="false" :style="spriteStyle" />
    </div>
    <div class="sprite-glow" :style="spriteGlowStyle" />

    <!-- 设置面板 -->
    <transition name="fade">
      <div v-if="showSettings" class="settings-panel">
        <div class="stitle">— 设置 —</div>
        <div class="srow">
          <span class="slabel">音量</span>
          <input type="range" min="0" max="100" v-model.number="volume" @input="onVolumeChange" />
          <span class="sval">{{ volume }}</span>
        </div>
        <div class="srow">
          <span class="slabel">称呼</span>
          <input type="text" v-model="doctorName" class="stext" placeholder="真理" maxlength="20" />
        </div>
        <div class="srow">
          <span class="slabel">立绘 X</span>
          <input type="range" min="-800" max="800" step="5" v-model.number="spriteX" />
          <span class="sval">{{ spriteX }}</span>
        </div>
        <div class="srow">
          <span class="slabel">立绘 Y</span>
          <input type="range" min="-700" max="700" step="5" v-model.number="spriteY" />
          <span class="sval">{{ spriteY }}</span>
        </div>
        <div class="srow">
          <span class="slabel">大小</span>
          <input type="range" min="30" max="400" step="5" :value="Math.round(spriteScale*100)"
                 @input="spriteScale = +($event.target.value/100).toFixed(2)" />
          <span class="sval">{{ (spriteScale*100).toFixed(0) }}%</span>
        </div>
        <div class="srow srow-end">
          <button class="sbtn-save" @click="saveAll">保存</button>
          <button @click="showSettings = false">关闭</button>
        </div>
      </div>
    </transition>

    <!-- 对话框 -->
    <footer class="panel">
      <!-- 拖拽把手 -->
      <div class="drag-handle" @mousedown="startDrag">⠿</div>

      <!-- 历史 -->
      <div class="history" ref="historyEl">
        <div v-for="(msg, i) in visibleHistory" :key="i" class="hline" :class="msg.role">
          <span class="hname">{{ msg.role === 'assistant' ? '凯尔希' : doctorName }}</span>
          <span class="htext">{{ msg.text }}</span>
        </div>
      </div>

      <!-- 当前发言 -->
      <div class="curline">
        <span class="cname">{{ currentSpeaker }}</span>
        <span class="csep"> — </span>
        <span class="ctext">{{ displayText }}</span>
        <span v-if="isTyping" class="caret" />
      </div>

      <div class="divider" />

      <!-- 输入行 -->
      <div class="irow">
        <input ref="inputEl" v-model="inputText" class="itext"
               placeholder="向凯尔希发送消息…" maxlength="500"
               @keydown.enter.prevent="submit" />
        <button class="ibtn" :class="{ active: isRecording }" @click="toggleMic">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"/>
          </svg>
        </button>
        <button class="ibtn send" :disabled="!inputText.trim() || isTyping" @click="submit">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 2 11 13M22 2 15 22l-4-9-9-4 20-7z"/>
          </svg>
        </button>
        <div class="tools">
          <button :class="{ tactive: showSettings }" @click="showSettings = !showSettings">⚙</button>
          <button @click="$emit('test-voice')">♪</button>
          <button @click="$emit('minimize')">─</button>
          <button class="tdanger" @click="$emit('close')">✕</button>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { setVolume } from '../api/voice.js'

const props = defineProps({
  messages: Array, isTyping: Boolean, currentText: String,
  touchText: String, touchActive: Boolean,
})
const emit = defineEmits(['send', 'close', 'minimize', 'test-voice', 'touch-sprite'])

const inputEl   = ref(null)
const historyEl = ref(null)
const inputText = ref('')
const isRecording  = ref(false)
const showSettings = ref(false)

// ── 设置 ──────────────────────────────────────────────────────
const SK = 'kaltsit_settings'
const _s = JSON.parse(localStorage.getItem(SK) || 'null') ?? { volume: 85, doctorName: '真理' }
const volume = ref(_s.volume), doctorName = ref(_s.doctorName)
function onVolumeChange() { setVolume(volume.value / 100) }
function saveAll() {
  localStorage.setItem(SK, JSON.stringify({ volume: volume.value, doctorName: doctorName.value }))
  saveSprite(); showSettings.value = false
}

// ── 立绘 ──────────────────────────────────────────────────────
const spriteUrl = 'http://127.0.0.1:8765/assets/%E7%AB%8B%E7%BB%98_%E5%87%AF%E5%B0%94%E5%B8%8C%C2%B7%E6%80%9D%E8%A1%A1%E6%89%98_1.png'
const PK = 'kaltsit_sprite'
// 坐标系原点：对应实际 x=-800, y=-700（立绘当前位置即 0,0）
const ORIGIN = { x: -800, y: -700 }

function loadSP() {
  try {
    const s = JSON.parse(localStorage.getItem(PK) || 'null')
    if (!s) return { x: 0, y: 0, scale: 4.0 }
    // 将存储的实际坐标转换为相对坐标
    return {
      x: (s.x ?? ORIGIN.x) - ORIGIN.x,
      y: (s.y ?? ORIGIN.y) - ORIGIN.y,
      scale: Math.max(0.3, Math.min(4.0, s.scale ?? 4.0)),
    }
  } catch { return { x: 0, y: 0, scale: 4.0 } }
}

function saveSprite() {
  // 存储时换算回实际坐标
  localStorage.setItem(PK, JSON.stringify({
    x: spriteX.value + ORIGIN.x,
    y: spriteY.value + ORIGIN.y,
    scale: spriteScale.value,
  }))
}
const _sp = loadSP()
const spriteX = ref(_sp.x), spriteY = ref(_sp.y), spriteScale = ref(_sp.scale)

// spriteStyle 直接绑定到 img 元素，控制图片本身的位置和大小
const spriteStyle    = computed(() => ({
  left:   (spriteX.value + ORIGIN.x) + 'px',
  bottom: (spriteY.value + ORIGIN.y) + 'px',
  height: (480 * spriteScale.value) + 'px',
}))
const spriteGlowStyle = computed(() => ({
  left:   (spriteX.value + ORIGIN.x + 60) + 'px',
  bottom: (spriteY.value + ORIGIN.y - 10) + 'px',
}))

function adjustScale(d) { spriteScale.value = +(Math.min(4.0, Math.max(0.3, spriteScale.value + d))).toFixed(2) }
function onSpriteTouch() { emit('touch-sprite') }

// ── 对话 ──────────────────────────────────────────────────────
const displayText = computed(() => {
  if (props.touchActive) return props.touchText
  if (props.isTyping)    return props.currentText
  return props.messages.at(-1)?.text ?? ''
})
const currentSpeaker = computed(() => {
  if (props.touchActive || props.isTyping) return '凯尔希'
  return props.messages.at(-1)?.role === 'assistant' ? '凯尔希' : doctorName.value
})
const visibleHistory = computed(() => {
  const a = props.messages
  return a.length > 1 ? a.slice(0, -1).slice(-5) : []
})
watch(() => props.messages.length, async () => {
  await nextTick()
  if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
})
function submit() {
  if (!inputText.value.trim() || props.isTyping) return
  emit('send', inputText.value.trim()); inputText.value = ''
  nextTick(() => inputEl.value?.focus())
}
function toggleMic() { isRecording.value = !isRecording.value }

// ── drag-handle IPC 拖拽（rAF 节流） ──────────────────────────
let _d = null, _raf = null
function startDrag(e) {
  e.preventDefault()
  _d = { px: e.screenX, py: e.screenY, dx: 0, dy: 0 }
  window.addEventListener('mousemove', _mv, { passive: true })
  window.addEventListener('mouseup', _mu)
}
function _mv(e) {
  if (!_d) return
  _d.dx += e.screenX - _d.px; _d.dy += e.screenY - _d.py
  _d.px = e.screenX; _d.py = e.screenY
  if (_raf) return
  _raf = requestAnimationFrame(() => {
    if (_d && (_d.dx || _d.dy)) {
      window.electronAPI?.dragWindow({ deltaX: _d.dx, deltaY: _d.dy })
      _d.dx = 0; _d.dy = 0
    }
    _raf = null
  })
}
function _mu() {
  _d = null
  if (_raf) { cancelAnimationFrame(_raf); _raf = null }
  window.removeEventListener('mousemove', _mv)
  window.removeEventListener('mouseup', _mu)
}
</script>

<style scoped>
/* ── 根容器，严格裁剪防止 Electron 窗口扩张 ── */
.chat-root {
  width: 500px;
  height: 700px;
  position: relative;
  overflow: hidden;
  contain: layout size;
  background: transparent;
  cursor: url('/cursors/PRTS - normal 正常选择.cur'), auto;
}

/* ── 指针 ── */
button { cursor: url('/cursors/PRTS - normal 正常选择.cur'), auto; }
button:hover { cursor: url('/cursors/Kaltsit-Link.ani'), pointer !important; }
input[type="text"], .stext, .itext { cursor: url('/cursors/PRTS - beam 文本选择.ani'), text !important; }
input[type="range"] { cursor: url('/cursors/PRTS - move 移动.cur'), ew-resize !important; }
.drag-handle { cursor: url('/cursors/PRTS - move 移动.cur'), move !important; }
button:disabled { cursor: url('/cursors/PRTS - unavail 不可用2.cur'), not-allowed !important; }
.sprite-wrap { cursor: url('/cursors/Kaltsit-Link.ani'), pointer; }

/* ── 立绘 ── */
.sprite-wrap {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 500px;
  height: 700px;
  overflow: hidden;
  pointer-events: all;
  user-select: none;
}
.sprite {
  position: absolute;
  bottom: 0;
  left: 0;
  width: auto;
  max-width: none;
  object-fit: contain;
  object-position: bottom left;
  filter: drop-shadow(0 8px 32px rgba(0,0,0,0.55));
  animation: breathe 6s ease-in-out infinite;
  pointer-events: none;
}
.sprite-glow {
  position: absolute;
  width: 200px;
  height: 50px;
  background: radial-gradient(ellipse, rgba(168,200,216,0.07), transparent 70%);
  pointer-events: none;
}

/* ── 设置面板 ── */
.settings-panel {
  position: absolute;
  bottom: 170px;
  right: 16px;
  width: 230px;
  background: rgba(6,8,13,0.97);
  border: 1px solid rgba(168,200,216,0.22);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  z-index: 30;
}
.stitle {
  font-size: 10px;
  letter-spacing: 0.25em;
  color: rgba(168,200,216,0.45);
  font-family: monospace;
  text-align: center;
  border-bottom: 1px solid rgba(168,200,216,0.1);
  padding-bottom: 7px;
}
.srow { display: flex; align-items: center; gap: 7px; }
.srow-end { justify-content: flex-end; gap: 8px; margin-top: 2px; }
.slabel { font-size: 10px; color: rgba(168,200,216,0.55); flex-shrink: 0; width: 46px; font-family: monospace; }
.sval { font-size: 10px; color: rgba(168,200,216,0.45); font-family: monospace; min-width: 26px; text-align: center; }
.stext { flex: 1; background: rgba(168,200,216,0.05); border: 1px solid rgba(168,200,216,0.18); color: rgba(220,230,236,0.9); font-size: 12px; padding: 3px 7px; outline: none; font-family: inherit; }
.stext:focus { border-color: rgba(168,200,216,0.45); }
.settings-panel button { background: transparent; border: 1px solid rgba(168,200,216,0.2); color: rgba(168,200,216,0.65); font-size: 11px; padding: 2px 9px; transition: all 0.12s; }
.settings-panel button:hover { border-color: rgba(168,200,216,0.55); color: #a8c8d8; }
.sbtn-save { border-color: rgba(168,200,216,0.38) !important; color: #a8c8d8 !important; }
.settings-panel input[type="range"] { flex: 1; height: 2px; accent-color: #a8c8d8; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(5px); }

/* ── 对话框 ── */
.panel {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: rgba(8,10,14,0.35);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid rgba(168,200,216,0.18);
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 20;
}
.drag-handle {
  position: absolute;
  top: 7px; right: 11px;
  width: 30px; height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: rgba(168,200,216,0.22);
  user-select: none;
  transition: color 0.15s;
}
.drag-handle:hover { color: rgba(168,200,216,0.7); }

.history { max-height: 52px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.hline { font-size: 11px; line-height: 1.5; display: flex; gap: 6px; color: rgba(168,200,216,0.3); }
.hname { flex-shrink: 0; font-family: monospace; font-size: 10px; color: rgba(168,200,216,0.42); }
.hline.user .hname { color: rgba(200,168,100,0.42); }
.htext { font-size: 11px; }

.curline { min-height: 50px; display: flex; align-items: baseline; padding: 2px 0 4px; }
.cname { font-family: monospace; font-size: 13px; letter-spacing: 0.12em; color: #a8c8d8; font-weight: 700; flex-shrink: 0; }
.csep { font-size: 12px; color: rgba(168,200,216,0.25); margin: 0 6px 0 4px; flex-shrink: 0; }
.ctext { font-size: 13px; line-height: 1.75; color: rgba(220,230,236,0.92); letter-spacing: 0.04em; }
.caret { display: inline-block; width: 2px; height: 14px; background: #a8c8d8; margin-left: 2px; vertical-align: middle; animation: blink 0.8s step-end infinite; }

.divider { height: 1px; background: rgba(168,200,216,0.1); }

.irow { display: flex; align-items: center; gap: 6px; }
.itext { flex: 1; background: transparent; border: none; outline: none; color: rgba(220,230,236,0.88); font-size: 12.5px; font-family: inherit; caret-color: #a8c8d8; padding: 2px 0; }
.itext::placeholder { color: rgba(168,200,216,0.2); }

.ibtn { width: 28px; height: 28px; flex-shrink: 0; background: transparent; border: 1px solid rgba(168,200,216,0.14); color: rgba(168,200,216,0.38); display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.ibtn svg { width: 13px; height: 13px; }
.ibtn:hover { border-color: rgba(168,200,216,0.5); color: #a8c8d8; }
.ibtn.active { border-color: #a8c8d8; color: #a8c8d8; }
.ibtn:disabled { opacity: 0.15; }

.tools { display: flex; gap: 2px; flex-shrink: 0; margin-left: 4px; padding-left: 8px; border-left: 1px solid rgba(168,200,216,0.1); }
.tools button { width: 22px; height: 22px; background: transparent; border: none; color: rgba(168,200,216,0.26); font-size: 11px; display: flex; align-items: center; justify-content: center; transition: color 0.15s; }
.tools button:hover { color: rgba(168,200,216,0.8); }
.tools .tactive { color: #a8c8d8; }
.tools .tdanger:hover { color: rgba(200,80,80,0.8); }
</style>
