<template>
  <main class="setup-canvas">
    <section class="setup-panel">
      <header class="setup-header">
        <div>
          <small>PRTS / INITIALIZATION SEQUENCE</small>
          <h1>终端初始化</h1>
        </div>
        <nav>
          <button type="button" aria-label="最小化" @click="minimizeWindow">—</button>
          <button type="button" aria-label="隐藏窗口" @click="hideWindow">×</button>
        </nav>
      </header>

      <div class="setup-progress" aria-label="初始化进度">
        <span :class="{ complete: state.assetsReady }">01 / 资源</span>
        <i />
        <span :class="{ complete: state.apiKeyConfigured }">02 / AI</span>
        <i />
        <span :class="{ complete: state.complete }">03 / 完成</span>
      </div>

      <section class="setup-intro">
        <small>LOCAL-FIRST COMPANION RUNTIME</small>
        <p>角色资源与密钥只保存在当前设备。资源不会上传，DeepSeek Key 使用 Windows 系统加密后写入本地配置。</p>
      </section>

      <div class="setup-grid">
        <section class="setup-step" :class="{ ready: state.assetsReady }">
          <header>
            <span>01</span>
            <div>
              <h2>导入角色资源</h2>
              <small>PORTRAIT / SPINE / VOICE</small>
            </div>
          </header>
          <p>选择项目的 <code>assets</code> 目录，或包含该目录的项目根目录。</p>
          <output>{{ assetStatus }}</output>
          <button type="button" class="step-action" :disabled="busy" @click="importAssets">
            {{ importing ? '正在复制资源…' : state.assetsReady ? '重新选择资源' : '选择资源目录' }}
          </button>
        </section>

        <section class="setup-step" :class="{ ready: state.apiKeyConfigured }">
          <header>
            <span>02</span>
            <div>
              <h2>连接 DeepSeek</h2>
              <small>ENCRYPTED LOCAL CREDENTIAL</small>
            </div>
          </header>
          <p>Key 仅在本机解密，并作为环境变量传给本地 AI 后端。</p>
          <label>
            <span>API KEY</span>
            <input
              v-model.trim="apiKey"
              type="password"
              autocomplete="off"
              :placeholder="state.apiKeyHint || 'sk-…'"
              @keydown.enter.prevent="saveKey"
            >
          </label>
          <button type="button" class="step-action" :disabled="busy || !apiKey" @click="saveKey">
            {{ savingKey ? '正在加密保存…' : state.apiKeyConfigured ? '更新密钥' : '加密保存' }}
          </button>
        </section>
      </div>

      <p v-if="message" class="setup-message" :class="{ error: hasError }">{{ message }}</p>

      <footer class="setup-footer">
        <button type="button" class="finish-button" :disabled="busy || !state.complete" @click="finishSetup">
          启动 PRTS
        </button>
      </footer>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const emit = defineEmits(['complete'])

const state = ref({
  complete: false,
  assetsReady: false,
  apiKeyConfigured: false,
  apiKeyHint: '',
  missingAssets: []
})
const apiKey = ref('')
const importing = ref(false)
const savingKey = ref(false)
const finishing = ref(false)
const message = ref('')
const hasError = ref(false)

const busy = computed(() => importing.value || savingKey.value || finishing.value)
const assetStatus = computed(() => {
  if (state.value.assetsReady) return '资源校验通过'
  const count = state.value.missingAssets?.length || 0
  return count ? `缺少 ${count} 个必要文件` : '尚未导入资源'
})

onMounted(refreshState)

async function refreshState() {
  const next = await window.electronAPI?.getSetupState()
  if (next) state.value = next
}

async function importAssets() {
  importing.value = true
  clearMessage()
  try {
    const result = await window.electronAPI?.importAssets()
    if (result?.setup) state.value = result.setup
    if (result?.canceled) return
    if (!result?.imported) throw new Error(result?.error || '资源导入失败')
    showMessage('资源复制与完整性校验已完成。')
  } catch (error) {
    showMessage(error.message || '资源导入失败', true)
  } finally {
    importing.value = false
  }
}

async function saveKey() {
  if (!apiKey.value) return
  savingKey.value = true
  clearMessage()
  try {
    state.value = await window.electronAPI.saveSetupApiKey(apiKey.value)
    apiKey.value = ''
    showMessage('DeepSeek Key 已使用系统加密保存。')
  } catch (error) {
    showMessage(error.message || '密钥保存失败', true)
  } finally {
    savingKey.value = false
  }
}

async function finishSetup() {
  if (!state.value.complete) return
  finishing.value = true
  clearMessage()
  try {
    const completed = await window.electronAPI.completeSetup()
    emit('complete', completed)
  } catch (error) {
    showMessage(error.message || '初始化未能完成', true)
    finishing.value = false
  }
}

function minimizeWindow() {
  window.electronAPI?.minimizeWindow()
}

function hideWindow() {
  window.electronAPI?.closeWindow()
}

function clearMessage() {
  message.value = ''
  hasError.value = false
}

function showMessage(text, error = false) {
  message.value = text
  hasError.value = error
}
</script>

<style scoped>
.setup-canvas {
  width: 860px;
  height: 700px;
  display: grid;
  place-items: center;
  padding: 12px;
  color: rgba(255, 255, 255, 0.92);
  background: transparent;
  cursor: url('/cursors/PRTS - normal 正常选择.cur'), auto;
}

.setup-panel {
  width: 836px;
  height: 676px;
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 27px 30px 24px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(3, 3, 3, 0.92);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 28px 80px rgba(0, 0, 0, 0.46);
  backdrop-filter: blur(28px) saturate(0);
  clip-path: polygon(0 0, calc(100% - 18px) 0, 100% 18px, 100% 100%, 0 100%);
}

.setup-panel::before {
  content: '';
  width: 96px;
  height: 1px;
  position: absolute;
  top: 0;
  left: 30px;
  background: white;
  box-shadow: 0 0 12px rgba(255, 255, 255, 0.72);
}

.setup-header,
.setup-footer,
.setup-step header,
.setup-progress {
  display: flex;
  align-items: center;
}

.setup-header {
  height: 65px;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  -webkit-app-region: drag;
}

.setup-header small,
.setup-intro small,
.setup-step small,
.setup-progress,
label > span {
  font-family: var(--font-display);
  font-size: 7px;
  letter-spacing: 0.16em;
  color: rgba(255, 255, 255, 0.34);
}

h1 {
  margin: 5px 0 0;
  font-size: 25px;
  font-weight: 520;
  letter-spacing: 0.09em;
}

.setup-header nav {
  display: flex;
  gap: 4px;
  -webkit-app-region: no-drag;
}

button {
  border: 0;
  color: rgba(255, 255, 255, 0.7);
  background: transparent;
  cursor: url('/cursors/PRTS - link 连接选择.cur'), pointer;
}

button:disabled { opacity: 0.22; cursor: not-allowed; }
.setup-header nav button { width: 30px; height: 28px; font-size: 15px; }
.setup-header nav button:hover { color: white; background: rgba(255, 255, 255, 0.07); }

.setup-progress {
  height: 43px;
  gap: 12px;
}

.setup-progress span { transition: color 180ms ease; }
.setup-progress span.complete { color: rgba(255, 255, 255, 0.9); }
.setup-progress i { width: 42px; height: 1px; background: rgba(255, 255, 255, 0.12); }

.setup-intro {
  padding: 18px 18px 17px;
  border-left: 1px solid rgba(255, 255, 255, 0.68);
  background: rgba(255, 255, 255, 0.025);
}

.setup-intro p {
  max-width: 590px;
  margin: 8px 0 0;
  color: rgba(255, 255, 255, 0.62);
  font-size: 10px;
  line-height: 1.8;
}

.setup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 14px;
}

.setup-step {
  min-height: 244px;
  display: flex;
  flex-direction: column;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.018);
  transition: border-color 180ms ease, background 180ms ease;
}

.setup-step.ready {
  border-color: rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.035);
}

.setup-step header { gap: 12px; }
.setup-step header > span { font: 22px/1 var(--font-display); color: rgba(255, 255, 255, 0.22); }
.setup-step.ready header > span { color: rgba(255, 255, 255, 0.82); text-shadow: 0 0 10px rgba(255, 255, 255, 0.38); }
.setup-step h2 { margin: 0 0 3px; font-size: 13px; font-weight: 520; letter-spacing: 0.06em; }
.setup-step p { min-height: 42px; margin: 18px 0 9px; color: rgba(255, 255, 255, 0.42); font-size: 9px; line-height: 1.7; }
.setup-step code { color: rgba(255, 255, 255, 0.75); font-family: var(--font-mono); }
.setup-step output { color: rgba(255, 255, 255, 0.58); font-size: 8px; }

label { display: grid; gap: 6px; margin-bottom: 10px; }
input {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  outline: 0;
  color: white;
  background: rgba(0, 0, 0, 0.35);
  font: 9px var(--font-mono);
  cursor: url('/cursors/PRTS - beam 文本选择.ani'), text;
}
input:focus { border-color: rgba(255, 255, 255, 0.52); }

.step-action,
.finish-button {
  height: 36px;
  margin-top: auto;
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 9px;
  letter-spacing: 0.08em;
}
.step-action:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.55); background: rgba(255, 255, 255, 0.05); }

.setup-message {
  height: 24px;
  margin: 10px 0 0;
  color: rgba(255, 255, 255, 0.62);
  font-size: 8px;
}
.setup-message.error { text-decoration: underline; text-decoration-thickness: 1px; }

.setup-footer {
  min-height: 58px;
  margin-top: auto;
  justify-content: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.finish-button { width: 150px; margin: 0; color: black; background: rgba(255, 255, 255, 0.92); font-weight: 650; }
</style>
