<template>
  <main class="companion-canvas">
    <section class="portrait-zone" aria-label="凯尔希立绘">
      <img
        ref="spriteEl"
        class="sprite"
        :src="spriteUrl"
        alt="凯尔希"
        draggable="false"
        :style="spriteStyle"
        @load="syncHitRegions"
        @click="onSpriteTouch"
      >
    </section>

    <section class="conversation-zone" data-hit-zone>
      <transition name="history-rise">
        <section
          v-if="historyOpen"
          ref="historyEl"
          class="history-panel"
          aria-label="历史消息"
          @mouseenter="cancelHistoryClose"
          @mouseleave="scheduleHistoryClose"
          @wheel.stop
        >
          <header>
            <span>对话记录</span>
            <small>SESSION LOG · {{ historyMessages.length.toString().padStart(2, '0') }}</small>
          </header>
          <div class="history-list">
            <p v-if="!historyMessages.length" class="history-empty">当前会话尚无历史消息</p>
            <article
              v-for="(message, index) in historyMessages"
              :key="`${message.role}-${index}`"
              :class="message.role"
            >
              <span>{{ message.role === 'assistant' ? '凯尔希' : doctorName }}</span>
              <p>{{ message.text }}</p>
              <div v-if="message.sources?.length" class="message-sources">
                <span v-for="source in message.sources" :key="`${source.document_id}-${source.position}`">
                  {{ source.title }} · {{ String(source.position + 1).padStart(2, '0') }}
                </span>
              </div>
            </article>
          </div>
        </section>
      </transition>

      <footer class="subtitle-dock" :class="{ focused: composerFocused }">
        <div class="dock-glow" />
        <div class="window-drag-handle" title="拖动窗口" />

        <header class="dock-head">
          <div class="speaker-lockup">
            <small>01 / ACTIVE CHANNEL</small>
            <strong>{{ currentSpeaker }}</strong>
          </div>

          <nav class="dock-controls" aria-label="窗口控制">
            <button type="button" aria-label="播放问候语音" title="播放问候语音" @click="$emit('test-voice')">
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M5 12H2V8h3l4-3v10l-4-3Z" />
                <path d="M12.5 7.2a4 4 0 0 1 0 5.6M15 5a7 7 0 0 1 0 10" />
              </svg>
            </button>
            <button type="button" :class="{ active: showSettings }" aria-label="打开设置" title="设置" @click="toggleSettings">
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M10 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z" />
                <path d="m16 11 .1-1-.1-1 1.7-1.4-1.5-2.5-2.1.8a7 7 0 0 0-1.7-1L12 2.7H8l-.4 2.2a7 7 0 0 0-1.7 1l-2.1-.8-1.5 2.5L4 9l-.1 1 .1 1-1.7 1.4 1.5 2.5 2.1-.8a7 7 0 0 0 1.7 1l.4 2.2h4l.4-2.2a7 7 0 0 0 1.7-1l2.1.8 1.5-2.5L16 11Z" />
              </svg>
            </button>
            <button type="button" aria-label="最小化" title="最小化" @click="$emit('minimize')">
              <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5h12" /></svg>
            </button>
            <button type="button" aria-label="返回桌宠" title="返回桌宠" @click="$emit('close')">
              <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" /></svg>
            </button>
          </nav>
        </header>

        <section
          class="subtitle-area"
          tabindex="0"
          aria-label="当前字幕，点击进入下一页"
          @mouseenter="openHistory"
          @mouseleave="scheduleHistoryClose"
          @focus="openHistory"
          @blur="scheduleHistoryClose"
          @click="advanceSubtitle"
          @keydown.space.prevent="advanceSubtitle"
          @keydown.enter.prevent="advanceSubtitle"
          @wheel.prevent="navigateSubtitle"
        >
          <span class="message-direction">{{ isTyping || isResponding ? 'TX' : 'RX' }}</span>
          <p>{{ displayText }}</p>
          <span v-if="isTyping" class="type-caret" />
          <div class="page-index" :class="{ visible: pageCount > 1 }">
            <span>{{ String(pageIndex + 1).padStart(2, '0') }}</span>
            <i />
            <span>{{ String(pageCount).padStart(2, '0') }}</span>
          </div>
        </section>

        <p v-if="errorText" class="error-line"><span>!</span>{{ errorText }}</p>

        <form class="composer" @submit.prevent="submit">
          <span class="prompt-mark">›</span>
          <input
            ref="inputEl"
            v-model="inputText"
            type="text"
            maxlength="500"
            autocomplete="off"
            :disabled="isBusy"
            placeholder="向凯尔希发送消息"
            @focus="composerFocused = true"
            @blur="composerFocused = false"
          >
          <button
            type="button"
            class="composer-button voice-button"
            disabled
            aria-label="本地语音输入尚未接入"
            title="本地语音识别模块尚未接入"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M10 2.5A2.5 2.5 0 0 0 7.5 5v5a2.5 2.5 0 0 0 5 0V5A2.5 2.5 0 0 0 10 2.5Z" />
              <path d="M15.5 9.5v.5a5.5 5.5 0 0 1-11 0v-.5M10 15.5v2M7.5 17.5h5" />
            </svg>
          </button>
          <button
            type="submit"
            class="composer-button send-button"
            :disabled="!canSend"
            aria-label="发送消息"
            title="发送"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m3 10 13-6-4.5 12-2-4-6.5-2ZM9.5 12 16 4" /></svg>
          </button>
        </form>

        <div class="dock-status">
          <span :class="`status-${runtimeStatus.backend}`">AI {{ backendLabel }}</span>
          <span>PET {{ petLabel }}</span>
          <span>{{ inputText.length.toString().padStart(3, '0') }} / 500</span>
        </div>
      </footer>
    </section>

    <transition name="wing-unfold">
      <aside v-if="showSettings" class="settings-wing" data-hit-zone aria-label="终端设置">
        <div class="wing-connector" />
        <header class="settings-head">
          <div>
            <small>LOCAL PREFERENCES / 01</small>
            <h2>设置</h2>
          </div>
          <button type="button" aria-label="关闭设置" title="关闭设置" @click="closeSettings">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" /></svg>
          </button>
        </header>

        <div class="settings-scroll">
          <section class="setting-section session-section">
            <header>
              <span>会话记录</span>
              <button type="button" :disabled="isBusy" @click="$emit('create-session')">新建</button>
            </header>
            <div class="session-list">
              <p v-if="!sessions.length" class="session-empty">尚无本地会话</p>
              <article
                v-for="session in sessions"
                :key="session.id"
                :class="{ active: session.id === currentSessionId }"
              >
                <div v-if="editingSessionId === session.id" class="session-edit">
                  <input
                    v-model.trim="editingTitle"
                    type="text"
                    maxlength="60"
                    @keydown.enter.prevent="commitSessionRename(session.id)"
                    @keydown.esc.prevent="cancelSessionRename"
                  >
                  <button type="button" @click="commitSessionRename(session.id)">保存</button>
                </div>
                <template v-else>
                  <button type="button" class="session-main" :disabled="isBusy" @click="$emit('select-session', session.id)">
                    <b>{{ session.title }}</b>
                    <small>{{ session.preview || '空会话' }}</small>
                  </button>
                  <div class="session-actions">
                    <button type="button" title="重命名" @click="beginSessionRename(session)">改</button>
                    <button type="button" title="删除会话" @click="requestSessionDelete(session.id)">
                      {{ deleteArmedId === session.id ? '确认' : '删' }}
                    </button>
                  </div>
                </template>
              </article>
            </div>
          </section>

          <section class="setting-section">
            <header>
              <span>对话身份</span>
              <small>IDENTITY</small>
            </header>
            <label class="text-setting">
              <span>
                <b>博士称呼</b>
                <small>仅保存在当前设备</small>
              </span>
              <input v-model.trim="doctorName" type="text" placeholder="博士" maxlength="20">
            </label>
          </section>

          <section class="setting-section">
            <header>
              <span>本地语音</span>
              <small>VOICE</small>
            </header>
            <label class="range-setting">
              <span>
                <b>播放音量</b>
                <small>角色语音与反馈音量</small>
              </span>
              <output>{{ volume }}%</output>
              <input v-model.number="volume" type="range" min="0" max="100" @input="onVolumeChange">
            </label>
          </section>

          <section class="setting-section knowledge-section">
            <header>
              <span>本地知识库</span>
              <small>{{ ragStatus.ready ? 'HYBRID SEARCH' : 'KEYWORD MODE' }}</small>
            </header>
            <div class="knowledge-model">
              <span>
                <b>语义模型</b>
                <small>{{ ragStatus.ready ? `READY · ${ragStatus.source?.toUpperCase()}` : 'BAAI / BGE SMALL ZH' }}</small>
              </span>
              <i :class="{ ready: ragStatus.ready }" />
            </div>
            <div class="knowledge-actions">
              <button type="button" :disabled="knowledgeBusy" @click="importKnowledgeFiles">导入资料</button>
              <button v-if="!ragStatus.ready" type="button" :disabled="knowledgeBusy" @click="downloadKnowledgeModel">下载模型</button>
              <button v-if="!ragStatus.ready" type="button" :disabled="knowledgeBusy" @click="importKnowledgeModel">手动导入</button>
            </div>
            <div class="knowledge-list">
              <p v-if="!knowledgeDocuments.length" class="knowledge-empty">尚未导入 txt / md / json 资料</p>
              <article v-for="document in knowledgeDocuments" :key="document.id">
                <span>
                  <b>{{ document.title }}</b>
                  <small>{{ document.source_type.toUpperCase() }} · {{ document.indexed_count }}/{{ document.chunk_count }} CHUNKS</small>
                </span>
                <button type="button" :disabled="knowledgeBusy" @click="requestKnowledgeDelete(document.id)">
                  {{ knowledgeDeleteArmedId === document.id ? '确认' : '移除' }}
                </button>
              </article>
            </div>
            <p v-if="knowledgeMessage" class="knowledge-message">{{ knowledgeMessage }}</p>
          </section>

          <section class="setting-section runtime-config-section">
            <header>
              <span>运行配置</span>
              <small>SECURE CONFIG</small>
            </header>
            <label class="secure-key-setting">
              <span>
                <b>DeepSeek API Key</b>
                <small>{{ secureConfig.apiKeyHint || '使用系统加密保存' }}</small>
              </span>
              <input
                v-model.trim="newApiKey"
                type="password"
                autocomplete="off"
                placeholder="输入新 Key"
              >
            </label>
            <div class="runtime-actions">
              <button type="button" :disabled="runtimeConfigBusy || !newApiKey" @click="saveSecureApiKey">更新密钥</button>
              <button type="button" :disabled="runtimeConfigBusy" @click="reimportAssets">重新导入资源</button>
            </div>
            <p v-if="runtimeConfigMessage" class="runtime-config-message">{{ runtimeConfigMessage }}</p>
          </section>

          <section class="setting-section portrait-settings">
            <header>
              <span>立绘校准</span>
              <button type="button" @click="resetSprite">复位</button>
            </header>
            <label class="compact-range">
              <span>横向</span>
              <input v-model.number="spriteX" type="range" min="-1000" max="500" step="5">
              <output>{{ spriteX }}</output>
            </label>
            <label class="compact-range">
              <span>纵向</span>
              <input v-model.number="spriteY" type="range" min="-800" max="500" step="5">
              <output>{{ spriteY }}</output>
            </label>
            <label class="compact-range">
              <span>缩放</span>
              <input
                type="range"
                min="30"
                max="400"
                step="5"
                :value="Math.round(spriteScale * 100)"
                @input="spriteScale = +($event.target.value / 100).toFixed(2)"
              >
              <output>{{ Math.round(spriteScale * 100) }}%</output>
            </label>
          </section>

          <section class="setting-section runtime-section">
            <header>
              <span>运行状态</span>
              <small>LOCAL RUNTIME</small>
            </header>
            <dl>
              <div><dt>AI 服务</dt><dd>{{ backendLabel }}</dd></div>
              <div><dt>桌宠服务</dt><dd>{{ petLabel }}</dd></div>
              <div><dt>语音识别</dt><dd>PENDING</dd></div>
            </dl>
          </section>
        </div>

        <footer class="settings-footer">
          <span :class="{ visible: savedNotice }">设置已保存</span>
          <button type="button" class="save-button" @click="saveAll">保存设置</button>
        </footer>
      </aside>
    </transition>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  deleteKnowledgeDocument,
  downloadRagModel,
  getKnowledgeDocuments,
  getRagStatus,
  importKnowledgeDocument,
  reloadRagModel
} from '../api/rag.js'
import { setVolume } from '../api/voice.js'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  isTyping: Boolean,
  isResponding: Boolean,
  isBusy: Boolean,
  currentText: { type: String, default: '' },
  pageIndex: { type: Number, default: 0 },
  pageCount: { type: Number, default: 1 },
  touchText: { type: String, default: '' },
  touchActive: Boolean,
  runtimeStatus: {
    type: Object,
    default: () => ({ backend: 'checking', pet: 'checking', aiConfigured: null })
  },
  errorText: { type: String, default: '' },
  sessions: { type: Array, default: () => [] },
  currentSessionId: { type: String, default: null }
})

const emit = defineEmits([
  'send',
  'next-page',
  'previous-page',
  'close',
  'minimize',
  'test-voice',
  'touch-sprite',
  'create-session',
  'select-session',
  'rename-session',
  'delete-session'
])

const spriteEl = ref(null)
const inputEl = ref(null)
const historyEl = ref(null)
const inputText = ref('')
const historyOpen = ref(false)
const showSettings = ref(false)
const composerFocused = ref(false)
const savedNotice = ref(false)
const newApiKey = ref('')
const runtimeConfigBusy = ref(false)
const runtimeConfigMessage = ref('')
const secureConfig = ref({ apiKeyConfigured: false, apiKeyHint: '' })
const editingSessionId = ref(null)
const editingTitle = ref('')
const deleteArmedId = ref(null)
const ragStatus = ref({ ready: false, source: null })
const knowledgeDocuments = ref([])
const knowledgeBusy = ref(false)
const knowledgeMessage = ref('')
const knowledgeDeleteArmedId = ref(null)

const SETTINGS_KEY = 'kaltsit_settings'
const SPRITE_KEY = 'kaltsit_sprite'
const DEFAULT_SPRITE = { x: -800, y: -600, scale: 4 }
const savedSettings = readStorage(SETTINGS_KEY, { volume: 85, doctorName: '博士' })
const savedSprite = loadSprite()
const volume = ref(savedSettings.volume ?? 85)
const doctorName = ref(savedSettings.doctorName || '博士')
const spriteX = ref(savedSprite.x)
const spriteY = ref(savedSprite.y)
const spriteScale = ref(savedSprite.scale)
const spriteUrl = 'http://127.0.0.1:8765/assets/illustration/%E7%AB%8B%E7%BB%98_%E5%87%AF%E5%B0%94%E5%B8%8C%C2%B7%E6%80%9D%E8%A1%A1%E6%89%98_1.png'

let historyCloseTimer
let settingsCollapseTimer
let savedNoticeTimer
let removeForceCloseListener

setVolume(volume.value / 100)

const spriteStyle = computed(() => ({
  left: `${spriteX.value}px`,
  bottom: `${spriteY.value}px`,
  height: `${480 * spriteScale.value}px`
}))

const displayText = computed(() => {
  if (props.touchActive) return props.touchText
  if (props.currentText) return props.currentText
  if (props.isResponding) return '正在建立神经链接……'
  return props.messages.at(-1)?.text || '通信频道已建立。'
})

const currentSpeaker = computed(() => {
  if (props.touchActive || props.isTyping || props.isResponding || props.currentText) return '凯尔希'
  return props.messages.at(-1)?.role === 'assistant' ? '凯尔希' : doctorName.value
})

const historyMessages = computed(() => {
  const messages = [...props.messages]
  if (!props.touchActive && props.currentText && messages.at(-1)?.role === 'assistant') messages.pop()
  return messages
})

const canSend = computed(() => {
  return Boolean(inputText.value.trim()) && !props.isBusy &&
    props.runtimeStatus.backend === 'ready' && props.runtimeStatus.aiConfigured !== false
})

const backendLabel = computed(() => {
  if (props.runtimeStatus.backend === 'ready' && props.runtimeStatus.aiConfigured === false) return 'NO KEY'
  return ({
    ready: 'READY',
    starting: 'STARTING',
    checking: 'CHECKING',
    error: 'OFFLINE'
  })[props.runtimeStatus.backend] || 'OFFLINE'
})

const petLabel = computed(() => ({
  ready: 'READY',
  starting: 'STARTING',
  checking: 'CHECKING',
  error: 'OFFLINE'
})[props.runtimeStatus.pet] || 'OFFLINE')

watch(() => props.messages.length, async () => {
  await nextTick()
  if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
})

watch(
  [spriteX, spriteY, spriteScale, historyOpen, showSettings],
  syncHitRegions,
  { immediate: true }
)

watch(() => props.runtimeStatus.backend, status => {
  if (status === 'ready') loadKnowledgeState()
})

onMounted(async () => {
  removeForceCloseListener = window.electronAPI?.onForceCloseSettings(forceCloseSettings)
  if (window.electronAPI?.getSecureConfig) {
    secureConfig.value = await window.electronAPI.getSecureConfig()
  }
  if (props.runtimeStatus.backend === 'ready') await loadKnowledgeState()
  syncHitRegions()
})

onUnmounted(() => {
  window.clearTimeout(historyCloseTimer)
  window.clearTimeout(settingsCollapseTimer)
  window.clearTimeout(savedNoticeTimer)
  removeForceCloseListener?.()
})

function readStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback
  } catch {
    return fallback
  }
}

function loadSprite() {
  const stored = readStorage(SPRITE_KEY, null)
  if (!stored || (
    stored.layoutVersion !== 2 &&
    stored.x <= -600 && stored.y <= -500 && stored.scale >= 3.5
  )) {
    return { ...DEFAULT_SPRITE }
  }
  const migratedY = stored.layoutVersion === 2 ? stored.y : (stored.y ?? -270) + 238
  return {
    x: Math.max(-1000, Math.min(500, stored.x ?? DEFAULT_SPRITE.x)),
    y: Math.max(-800, Math.min(500, migratedY)),
    scale: Math.max(0.3, Math.min(4, stored.scale ?? DEFAULT_SPRITE.scale))
  }
}

function openHistory() {
  if (showSettings.value) return
  cancelHistoryClose()
  historyOpen.value = true
}

function scheduleHistoryClose() {
  cancelHistoryClose()
  if (composerFocused.value) return
  historyCloseTimer = window.setTimeout(() => { historyOpen.value = false }, 300)
}

function cancelHistoryClose() {
  window.clearTimeout(historyCloseTimer)
}

function advanceSubtitle() {
  emit('next-page')
}

function navigateSubtitle(event) {
  if (event.deltaY < 0) emit('previous-page')
  else if (event.deltaY > 0) emit('next-page')
}

function submit() {
  const text = inputText.value.trim()
  if (!text || !canSend.value) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => inputEl.value?.focus())
}

function onSpriteTouch() {
  emit('touch-sprite')
}

function toggleSettings() {
  if (showSettings.value) closeSettings()
  else openSettings()
}

function openSettings() {
  window.clearTimeout(settingsCollapseTimer)
  historyOpen.value = false
  window.electronAPI?.setSettingsExpanded(true)
  requestAnimationFrame(() => { showSettings.value = true })
}

function closeSettings() {
  showSettings.value = false
  settingsCollapseTimer = window.setTimeout(() => {
    window.electronAPI?.setSettingsExpanded(false)
  }, 320)
}

function forceCloseSettings() {
  window.clearTimeout(settingsCollapseTimer)
  showSettings.value = false
}

function onVolumeChange() {
  setVolume(volume.value / 100)
}

function resetSprite() {
  spriteX.value = DEFAULT_SPRITE.x
  spriteY.value = DEFAULT_SPRITE.y
  spriteScale.value = DEFAULT_SPRITE.scale
}

function beginSessionRename(session) {
  deleteArmedId.value = null
  editingSessionId.value = session.id
  editingTitle.value = session.title
}

function cancelSessionRename() {
  editingSessionId.value = null
  editingTitle.value = ''
}

function commitSessionRename(sessionId) {
  const title = editingTitle.value.trim()
  if (title) emit('rename-session', { id: sessionId, title })
  cancelSessionRename()
}

function requestSessionDelete(sessionId) {
  if (deleteArmedId.value !== sessionId) {
    deleteArmedId.value = sessionId
    return
  }
  deleteArmedId.value = null
  emit('delete-session', sessionId)
}

async function saveSecureApiKey() {
  if (!newApiKey.value) return
  runtimeConfigBusy.value = true
  runtimeConfigMessage.value = ''
  try {
    secureConfig.value = await window.electronAPI.saveApiKey(newApiKey.value)
    newApiKey.value = ''
    runtimeConfigMessage.value = '密钥已加密保存，AI 服务正在重启。'
  } catch (error) {
    runtimeConfigMessage.value = error.message || '密钥更新失败'
  } finally {
    runtimeConfigBusy.value = false
  }
}

async function reimportAssets() {
  runtimeConfigBusy.value = true
  runtimeConfigMessage.value = ''
  try {
    const result = await window.electronAPI.reimportAssets()
    if (result?.canceled) return
    if (!result?.imported) throw new Error(result?.error || '资源导入失败')
    runtimeConfigMessage.value = '资源已更新，本地运行时正在重启。'
  } catch (error) {
    runtimeConfigMessage.value = error.message || '资源导入失败'
  } finally {
    runtimeConfigBusy.value = false
  }
}

async function loadKnowledgeState() {
  try {
    const [status, documents] = await Promise.all([
      getRagStatus(),
      getKnowledgeDocuments()
    ])
    ragStatus.value = status
    knowledgeDocuments.value = documents
  } catch (error) {
    console.warn('[knowledge] 状态读取失败:', error.message)
  }
}

async function importKnowledgeFiles() {
  knowledgeBusy.value = true
  knowledgeMessage.value = ''
  try {
    const result = await window.electronAPI.selectKnowledgeFiles()
    if (result?.canceled) return
    if (result?.error) throw new Error(result.error)
    for (const file of result.files || []) {
      await importKnowledgeDocument(file)
    }
    await loadKnowledgeState()
    knowledgeMessage.value = `已导入 ${result.files?.length || 0} 个文件。`
  } catch (error) {
    knowledgeMessage.value = getRequestError(error, '资料导入失败')
  } finally {
    knowledgeBusy.value = false
  }
}

async function downloadKnowledgeModel() {
  knowledgeBusy.value = true
  knowledgeMessage.value = '正在下载并初始化语义模型，请保持网络连接。'
  try {
    if (window.electronAPI?.downloadEmbeddingModel) {
      await window.electronAPI.downloadEmbeddingModel()
      ragStatus.value = await reloadRagModel()
    } else {
      ragStatus.value = await downloadRagModel()
    }
    await loadKnowledgeState()
    knowledgeMessage.value = '语义模型已就绪，现有资料已完成索引。'
  } catch (error) {
    knowledgeMessage.value = getRequestError(error, '模型下载失败')
  } finally {
    knowledgeBusy.value = false
  }
}

async function importKnowledgeModel() {
  knowledgeBusy.value = true
  knowledgeMessage.value = ''
  try {
    const result = await window.electronAPI.importEmbeddingModel()
    if (result?.canceled) return
    if (!result?.imported) throw new Error(result?.error || '模型导入失败')
    knowledgeMessage.value = '模型已导入，AI 服务正在重启并补齐索引。'
  } catch (error) {
    knowledgeMessage.value = getRequestError(error, '模型导入失败')
  } finally {
    knowledgeBusy.value = false
  }
}

async function requestKnowledgeDelete(documentId) {
  if (knowledgeDeleteArmedId.value !== documentId) {
    knowledgeDeleteArmedId.value = documentId
    return
  }
  knowledgeDeleteArmedId.value = null
  knowledgeBusy.value = true
  knowledgeMessage.value = ''
  try {
    await deleteKnowledgeDocument(documentId)
    await loadKnowledgeState()
  } catch (error) {
    knowledgeMessage.value = getRequestError(error, '资料移除失败')
  } finally {
    knowledgeBusy.value = false
  }
}

function getRequestError(error, fallback) {
  return error.response?.data?.detail || error.message || fallback
}

function saveAll() {
  const safeDoctorName = doctorName.value || '博士'
  doctorName.value = safeDoctorName
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({
    volume: volume.value,
    doctorName: safeDoctorName
  }))
  localStorage.setItem(SPRITE_KEY, JSON.stringify({
    x: spriteX.value,
    y: spriteY.value,
    scale: spriteScale.value,
    layoutVersion: 2
  }))
  savedNotice.value = true
  window.clearTimeout(savedNoticeTimer)
  savedNoticeTimer = window.setTimeout(() => { savedNotice.value = false }, 1600)
}

function syncHitRegions() {
  const image = spriteEl.value
  const height = 480 * spriteScale.value
  const aspectRatio = image?.naturalWidth && image?.naturalHeight
    ? image.naturalWidth / image.naturalHeight
    : 1
  window.electronAPI?.updateHitRegions({
    sprite: {
      x: spriteX.value,
      y: 700 - spriteY.value - height,
      width: height * aspectRatio,
      height
    },
    historyOpen: historyOpen.value,
    settingsOpen: showSettings.value
  })
}
</script>

<style scoped>
.companion-canvas {
  width: 100vw;
  height: 700px;
  position: relative;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.94);
  background: transparent;
  cursor: url('/cursors/PRTS - normal 正常选择.cur'), auto;
}

.portrait-zone {
  width: 500px;
  height: 700px;
  position: absolute;
  inset: 0 auto 0 0;
  overflow: hidden;
  pointer-events: none;
}

.sprite {
  position: absolute;
  width: auto;
  max-width: none;
  object-fit: contain;
  pointer-events: auto;
  user-select: none;
  filter: drop-shadow(0 18px 38px rgba(0, 0, 0, 0.4));
  animation: portrait-breathe 7s ease-in-out infinite;
  cursor: url('/cursors/PRTS - link 连接选择.cur'), pointer;
}

.conversation-zone {
  width: 476px;
  height: 304px;
  position: absolute;
  z-index: 10;
  bottom: 12px;
  left: 12px;
  pointer-events: none;
}

.subtitle-dock,
.history-panel {
  pointer-events: auto;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(3, 3, 3, 0.79);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025), 0 20px 46px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(24px) saturate(0);
  -webkit-backdrop-filter: blur(24px) saturate(0);
}

.subtitle-dock {
  width: 100%;
  height: 160px;
  position: absolute;
  bottom: 0;
  left: 0;
  padding: 13px 14px 8px;
  clip-path: polygon(0 0, calc(100% - 13px) 0, 100% 13px, 100% 100%, 0 100%);
}

.subtitle-dock::before {
  content: '';
  width: 54px;
  height: 1px;
  position: absolute;
  top: 0;
  left: 14px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 0 9px rgba(255, 255, 255, 0.6);
}

.dock-glow {
  width: 120px;
  height: 24px;
  position: absolute;
  top: -12px;
  left: -20px;
  opacity: 0.18;
  background: radial-gradient(ellipse, rgba(255, 255, 255, 0.42), transparent 70%);
  pointer-events: none;
}

.window-drag-handle {
  width: 64px;
  height: 13px;
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  -webkit-app-region: drag;
  cursor: url('/cursors/PRTS - move 移动.cur'), move;
}

.window-drag-handle::after {
  content: '';
  width: 30px;
  height: 1px;
  position: absolute;
  top: 5px;
  left: 17px;
  background: rgba(255, 255, 255, 0.18);
  transition: background 180ms ease, box-shadow 180ms ease;
}

.window-drag-handle:hover::after {
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.35);
}

.dock-head {
  height: 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.speaker-lockup {
  display: flex;
  align-items: baseline;
  gap: 9px;
}

.speaker-lockup small,
.dock-status,
.settings-head small,
.setting-section > header small,
.history-panel header small {
  color: rgba(255, 255, 255, 0.32);
  font-family: var(--font-display);
  font-size: 6.5px;
  letter-spacing: 0.14em;
}

.speaker-lockup strong {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.dock-controls {
  display: flex;
  gap: 2px;
  opacity: 0;
  transform: translateY(-3px);
  transition: opacity 200ms ease, transform 240ms cubic-bezier(0.22, 1, 0.36, 1);
  -webkit-app-region: no-drag;
}

.subtitle-dock:hover .dock-controls,
.subtitle-dock:focus-within .dock-controls {
  opacity: 1;
  transform: translateY(0);
}

button {
  border: 0;
  color: rgba(255, 255, 255, 0.48);
  background: transparent;
  cursor: url('/cursors/PRTS - link 连接选择.cur'), pointer;
}

button:active:not(:disabled) { transform: scale(0.94); }

.dock-controls button,
.settings-head button {
  width: 24px;
  height: 22px;
  display: grid;
  place-items: center;
  transition: color 180ms ease, background 180ms ease, transform 120ms ease;
}

.dock-controls button:hover,
.dock-controls button.active,
.settings-head button:hover {
  color: rgba(255, 255, 255, 0.95);
  background: rgba(255, 255, 255, 0.07);
}

button svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.2;
}

.subtitle-area {
  height: 61px;
  position: relative;
  display: grid;
  grid-template-columns: 20px 1fr 38px;
  align-items: start;
  gap: 7px;
  padding: 5px 0 4px;
  outline: none;
  cursor: url('/cursors/PRTS - link 连接选择.cur'), pointer;
}

.subtitle-area:focus-visible::after {
  content: '';
  position: absolute;
  inset: 1px -4px;
  border: 1px solid rgba(255, 255, 255, 0.45);
}

.message-direction {
  padding-top: 3px;
  color: rgba(255, 255, 255, 0.36);
  font-family: var(--font-display);
  font-size: 6px;
  letter-spacing: 0.08em;
}

.subtitle-area > p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.91);
  font-size: 11.5px;
  line-height: 1.65;
  letter-spacing: 0.012em;
  text-wrap: pretty;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.type-caret {
  width: 1px;
  height: 13px;
  position: absolute;
  right: 41px;
  bottom: 9px;
  background: white;
  box-shadow: 0 0 7px rgba(255, 255, 255, 0.8);
  animation: caret-blink 760ms step-end infinite;
}

.page-index {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding-top: 3px;
  opacity: 0;
  color: rgba(255, 255, 255, 0.36);
  font-family: var(--font-display);
  font-size: 6px;
  font-variant-numeric: tabular-nums;
  transition: opacity 180ms ease;
}

.page-index.visible { opacity: 1; }
.page-index i { width: 7px; height: 1px; background: rgba(255, 255, 255, 0.25); }

.error-line {
  height: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -2px 0 3px;
  padding: 0 6px;
  color: rgba(255, 255, 255, 0.68);
  border-left: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.035);
  font-size: 7.5px;
  animation: error-flash 240ms ease 2;
}

.error-line span { font-family: var(--font-mono); }

.composer {
  height: 33px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 3px 3px 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.18);
  transition: border-color 200ms ease, background 200ms ease;
}

.composer:focus-within {
  border-color: rgba(255, 255, 255, 0.38);
  background: rgba(255, 255, 255, 0.025);
}

.prompt-mark {
  color: rgba(255, 255, 255, 0.76);
  font-family: var(--font-mono);
  font-size: 15px;
  text-shadow: 0 0 7px rgba(255, 255, 255, 0.45);
}

.composer input {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  outline: 0;
  color: rgba(255, 255, 255, 0.9);
  background: transparent;
  font: 10px/1.4 var(--font-sans);
  caret-color: white;
  cursor: url('/cursors/PRTS - beam 文本选择.ani'), text;
}

.composer input::placeholder { color: rgba(255, 255, 255, 0.22); }

.composer-button {
  width: 26px;
  height: 25px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  transition: color 180ms ease, background 180ms ease, opacity 180ms ease, transform 120ms ease;
}

.composer-button:hover:not(:disabled) {
  color: white;
  background: rgba(255, 255, 255, 0.07);
}

.send-button:not(:disabled) {
  color: rgba(0, 0, 0, 0.9);
  background: rgba(255, 255, 255, 0.9);
  clip-path: polygon(0 0, calc(100% - 6px) 0, 100% 6px, 100% 100%, 0 100%);
}

.composer-button:disabled { opacity: 0.16; cursor: not-allowed; }

.dock-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 5px;
  font-family: var(--font-display);
}

.dock-status span:last-child { margin-left: auto; }
.status-ready { color: rgba(255, 255, 255, 0.55); }
.status-starting,
.status-checking { animation: status-pulse 1.2s ease-in-out infinite; }
.status-error { text-decoration: line-through; text-decoration-thickness: 1px; }

.history-panel {
  width: 100%;
  height: 144px;
  position: absolute;
  bottom: 158px;
  left: 0;
  overflow: hidden;
  padding: 12px 14px;
  clip-path: polygon(0 0, 100% 0, 100% 100%, 12px 100%, 0 calc(100% - 12px));
}

.history-panel::after {
  content: '';
  width: 1px;
  position: absolute;
  top: 12px;
  right: 0;
  bottom: 14px;
  background: rgba(255, 255, 255, 0.42);
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.24);
}

.history-panel > header {
  height: 22px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.68);
  font-size: 9px;
}

.history-list {
  height: 96px;
  overflow-y: auto;
  padding: 7px 3px 3px 0;
}

.history-list article {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 8px;
  margin-bottom: 7px;
  color: rgba(255, 255, 255, 0.42);
  font-size: 8.5px;
  line-height: 1.55;
}

.history-list article > span {
  color: rgba(255, 255, 255, 0.65);
  font-family: var(--font-sans);
  font-size: 7px;
  letter-spacing: 0.08em;
}

.history-list article.user > span { color: rgba(255, 255, 255, 0.4); }
.history-list article p { margin: 0; }
.message-sources {
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: -3px;
}
.message-sources span {
  padding: 2px 4px;
  border-left: 1px solid rgba(255, 255, 255, 0.28);
  color: rgba(255, 255, 255, 0.32);
  background: rgba(255, 255, 255, 0.025);
  font: 5.8px var(--font-mono);
}
.history-empty { margin: 29px 0 0; color: rgba(255, 255, 255, 0.22); text-align: center; font-size: 8px; }

.history-rise-enter-active,
.history-rise-leave-active {
  transform-origin: bottom center;
  transition: opacity 200ms ease, transform 280ms cubic-bezier(0.22, 1, 0.36, 1);
}

.history-rise-enter-from,
.history-rise-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

.settings-wing {
  width: 336px;
  height: 676px;
  position: absolute;
  z-index: 20;
  top: 12px;
  left: 512px;
  display: flex;
  flex-direction: column;
  padding: 18px 17px 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(255, 255, 255, 0.9);
  background: rgba(3, 3, 3, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), 0 22px 60px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(28px) saturate(0);
  -webkit-backdrop-filter: blur(28px) saturate(0);
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 0 100%);
}

.settings-wing::before {
  content: '';
  width: 62px;
  height: 1px;
  position: absolute;
  top: 0;
  left: 18px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.48);
}

.wing-connector {
  width: 25px;
  height: 1px;
  position: absolute;
  bottom: 91px;
  left: -25px;
  background: rgba(255, 255, 255, 0.66);
  box-shadow: 0 0 7px rgba(255, 255, 255, 0.3);
}

.settings-head {
  height: 54px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.settings-head h2 {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 520;
  letter-spacing: 0.08em;
}

.settings-head small,
.setting-section > header small,
.history-panel header small {
  font-weight: 500;
}

.settings-scroll {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 14px 2px 12px 0;
}

.setting-section {
  margin-bottom: 11px;
  padding: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.022);
}

.setting-section > header {
  min-height: 23px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  color: rgba(255, 255, 255, 0.66);
  font-size: 9px;
  letter-spacing: 0.08em;
}

.setting-section > header button {
  padding: 2px 0;
  color: rgba(255, 255, 255, 0.4);
  font-size: 7px;
  letter-spacing: 0.08em;
}

.session-list {
  max-height: 154px;
  overflow-y: auto;
  margin-top: 5px;
}

.session-list article {
  min-height: 42px;
  display: flex;
  align-items: stretch;
  margin-bottom: 3px;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.16);
}
.session-list article.active { border-left-color: rgba(255, 255, 255, 0.72); background: rgba(255, 255, 255, 0.04); }
.session-main { min-width: 0; flex: 1; padding: 7px 8px; text-align: left; }
.session-main b,
.session-main small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-main b { color: rgba(255, 255, 255, 0.72); font-size: 8px; font-weight: 520; }
.session-main small { max-width: 195px; margin-top: 4px; color: rgba(255, 255, 255, 0.25); font-size: 6.5px; }
.session-actions { display: flex; align-items: center; padding-right: 3px; opacity: 0; transition: opacity 160ms ease; }
.session-list article:hover .session-actions,
.session-list article.active .session-actions { opacity: 1; }
.session-actions button { width: 29px; height: 26px; color: rgba(255, 255, 255, 0.35); font-size: 6.5px; }
.session-actions button:hover { color: white; background: rgba(255, 255, 255, 0.05); }
.session-edit { width: 100%; display: grid; grid-template-columns: 1fr 42px; gap: 4px; padding: 5px; }
.session-edit input {
  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.24);
  outline: 0;
  color: white;
  background: rgba(0, 0, 0, 0.35);
  padding: 0 6px;
  font-size: 7.5px;
}
.session-edit button { border: 1px solid rgba(255, 255, 255, 0.15); font-size: 6.5px; }
.session-empty { margin: 20px 0; color: rgba(255, 255, 255, 0.2); font-size: 7px; text-align: center; }

.knowledge-model {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 8px;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.17);
}
.knowledge-model span,
.knowledge-list article > span { min-width: 0; }
.knowledge-model b,
.knowledge-model small,
.knowledge-list b,
.knowledge-list small { display: block; }
.knowledge-model b,
.knowledge-list b {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.72);
  font-size: 8px;
  font-weight: 520;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.knowledge-model small,
.knowledge-list small {
  margin-top: 3px;
  color: rgba(255, 255, 255, 0.25);
  font: 5.8px var(--font-mono);
}
.knowledge-model i {
  width: 5px;
  height: 5px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  transform: rotate(45deg);
}
.knowledge-model i.ready {
  border-color: rgba(255, 255, 255, 0.85);
  background: white;
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.65);
}
.knowledge-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  margin-top: 5px;
}
.knowledge-actions button,
.knowledge-list button {
  min-height: 25px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.018);
  font-size: 6.3px;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease, transform 100ms ease;
}
.knowledge-actions button:hover,
.knowledge-list button:hover {
  border-color: rgba(255, 255, 255, 0.28);
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.045);
}
.knowledge-actions button:active,
.knowledge-list button:active { transform: translateY(1px); }
.knowledge-actions button:disabled,
.knowledge-list button:disabled { opacity: 0.28; }
.knowledge-list {
  max-height: 112px;
  overflow-y: auto;
  margin-top: 5px;
}
.knowledge-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 38px;
  align-items: center;
  gap: 5px;
  min-height: 38px;
  margin-bottom: 3px;
  padding-left: 8px;
  background: rgba(0, 0, 0, 0.14);
}
.knowledge-list article > button { height: 28px; border-width: 0 0 0 1px; }
.knowledge-empty {
  margin: 17px 0;
  color: rgba(255, 255, 255, 0.2);
  font-size: 7px;
  text-align: center;
}
.knowledge-message,
.runtime-config-message {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.42);
  font-size: 6.5px;
  line-height: 1.5;
}

.text-setting,
.range-setting {
  display: grid;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
}

.text-setting { grid-template-columns: 1fr 112px; }
.range-setting { grid-template-columns: 1fr 34px; }

.text-setting b,
.range-setting b {
  display: block;
  color: rgba(255, 255, 255, 0.82);
  font-size: 9px;
  font-weight: 520;
}

.text-setting small,
.range-setting small {
  display: block;
  margin-top: 3px;
  color: rgba(255, 255, 255, 0.28);
  font-size: 7px;
}

.text-setting input {
  width: 100%;
  padding: 7px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  outline: none;
  color: rgba(255, 255, 255, 0.86);
  background: rgba(0, 0, 0, 0.26);
  font-size: 9px;
}

.text-setting input:focus { border-color: rgba(255, 255, 255, 0.45); }

.secure-key-setting {
  display: grid;
  gap: 7px;
  padding-top: 8px;
}

.secure-key-setting span { display: flex; align-items: baseline; justify-content: space-between; }
.secure-key-setting b { color: rgba(255, 255, 255, 0.82); font-size: 9px; font-weight: 520; }
.secure-key-setting small { color: rgba(255, 255, 255, 0.28); font: 6.5px var(--font-mono); }
.secure-key-setting input {
  width: 100%;
  padding: 7px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  outline: 0;
  color: rgba(255, 255, 255, 0.86);
  background: rgba(0, 0, 0, 0.26);
  font: 8px var(--font-mono);
}
.secure-key-setting input:focus { border-color: rgba(255, 255, 255, 0.45); }

.runtime-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 7px; }
.runtime-actions button {
  min-height: 27px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  color: rgba(255, 255, 255, 0.55);
  font-size: 7px;
}
.runtime-actions button:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.38); color: white; }
.runtime-actions button:disabled { opacity: 0.2; }
.runtime-config-message { margin: 7px 0 0; color: rgba(255, 255, 255, 0.42); font-size: 7px; line-height: 1.5; }

.range-setting output,
.compact-range output {
  color: rgba(255, 255, 255, 0.45);
  font-family: var(--font-display);
  font-size: 7px;
  text-align: right;
}

.range-setting input { grid-column: 1 / -1; }

input[type='range'] {
  width: 100%;
  height: 2px;
  accent-color: white;
  cursor: url('/cursors/PRTS - move 移动.cur'), ew-resize;
}

.compact-range {
  display: grid;
  grid-template-columns: 31px 1fr 34px;
  align-items: center;
  gap: 8px;
  min-height: 27px;
  color: rgba(255, 255, 255, 0.38);
  font-size: 7.5px;
}

.runtime-section dl { margin: 4px 0 0; }
.runtime-section dl div { display: flex; justify-content: space-between; padding: 7px 0; border-top: 1px solid rgba(255, 255, 255, 0.06); }
.runtime-section dt { color: rgba(255, 255, 255, 0.38); font-size: 8px; }
.runtime-section dd { margin: 0; color: rgba(255, 255, 255, 0.62); font-family: var(--font-display); font-size: 7px; }

.settings-footer {
  height: 46px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.settings-footer > span {
  padding-bottom: 9px;
  color: rgba(255, 255, 255, 0.48);
  font-size: 7.5px;
  opacity: 0;
  transition: opacity 180ms ease;
}

.settings-footer > span.visible { opacity: 1; }

.save-button {
  min-width: 102px;
  height: 32px;
  color: rgba(0, 0, 0, 0.92);
  background: rgba(255, 255, 255, 0.9);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  clip-path: polygon(0 0, calc(100% - 7px) 0, 100% 7px, 100% 100%, 0 100%);
}

.wing-unfold-enter-active,
.wing-unfold-leave-active {
  transform-origin: left bottom;
  transition: opacity 220ms ease, transform 320ms cubic-bezier(0.22, 1, 0.36, 1), clip-path 320ms cubic-bezier(0.22, 1, 0.36, 1);
}

.wing-unfold-enter-from,
.wing-unfold-leave-to {
  opacity: 0;
  transform: translateX(-18px) scaleX(0.96);
  clip-path: polygon(0 84%, 0 84%, 0 100%, 0 100%, 0 100%);
}

@keyframes portrait-breathe {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes caret-blink {
  0%, 46% { opacity: 1; }
  47%, 100% { opacity: 0; }
}

@keyframes status-pulse {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 0.65; }
}

@keyframes error-flash {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .sprite,
  .type-caret,
  .status-starting,
  .status-checking,
  .error-line { animation: none; }

  *,
  *::before,
  *::after { transition-duration: 0.01ms !important; }
}
</style>
