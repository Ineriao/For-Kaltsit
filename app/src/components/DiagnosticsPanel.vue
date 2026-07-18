<template>
  <section class="diagnostics-console" aria-label="诊断与恢复">
    <header class="diagnostics-head">
      <span><small>RUNTIME CONTROL / LOCAL</small><b>诊断与恢复</b></span>
      <button type="button" :disabled="busy" @click="refresh">刷新</button>
    </header>

    <section class="diagnostic-block">
      <header><span>三进程状态</span><small>{{ uptimeLabel }}</small></header>
      <dl class="runtime-grid">
        <div><dt>Electron</dt><dd>READY</dd></div>
        <div><dt>FastAPI</dt><dd>{{ statusLabel(snapshot.runtime?.status?.backend) }}</dd></div>
        <div><dt>Java / Spine</dt><dd>{{ statusLabel(snapshot.runtime?.status?.pet) }}</dd></div>
      </dl>
      <div class="diagnostic-actions">
        <button type="button" :disabled="busy || interactionBusy" @click="restartService('backend')">重启后端</button>
        <button type="button" :disabled="busy || interactionBusy || snapshot.safeMode" @click="restartService('pet')">重启桌宠</button>
      </div>
      <label class="safe-mode-setting">
        <span><b>安全模式</b><small>关闭 Java 桌宠，仅保留界面与后端</small></span>
        <input v-model="safeMode" type="checkbox" :disabled="busy || interactionBusy" @change="changeSafeMode">
      </label>
    </section>

    <section class="diagnostic-block">
      <header><span>应用更新</span><small>GITHUB RELEASES</small></header>
      <div class="update-state">
        <span>
          <b>v{{ updateState.currentVersion || snapshot.app?.version || '1.0.0' }}</b>
          <small>{{ updateState.message || '尚未检查更新' }}</small>
        </span>
        <output v-if="updateState.status === 'downloading'">{{ Math.round(updateState.progress || 0) }}%</output>
      </div>
      <div v-if="updateState.status === 'downloading'" class="update-progress">
        <i :style="{ width: `${updateState.progress || 0}%` }" />
      </div>
      <div class="diagnostic-actions">
        <button type="button" :disabled="busy || updateState.status === 'checking'" @click="checkUpdates">检查更新</button>
        <button type="button" :disabled="busy || updateState.status !== 'available'" @click="downloadUpdate">下载</button>
        <button type="button" :disabled="busy || interactionBusy || updateState.status !== 'downloaded'" @click="installUpdate">
          {{ installArmed ? '确认重启安装' : '安装' }}
        </button>
      </div>
    </section>

    <section class="diagnostic-block">
      <header><span>数据状态</span><small>SQLITE / LOCAL</small></header>
      <dl class="data-grid">
        <div><dt>完整性</dt><dd>{{ backendDiagnostics?.integrity || '—' }}</dd></div>
        <div><dt>数据库</dt><dd>{{ formatBytes(backendDiagnostics?.database_size) }}</dd></div>
        <div><dt>会话</dt><dd>{{ backendDiagnostics?.counts?.sessions ?? '—' }}</dd></div>
        <div><dt>记忆</dt><dd>{{ backendDiagnostics?.counts?.memories ?? '—' }}</dd></div>
        <div><dt>资料</dt><dd>{{ backendDiagnostics?.counts?.documents ?? '—' }}</dd></div>
        <div><dt>备份</dt><dd>{{ backups.length }}</dd></div>
      </dl>
      <div class="diagnostic-actions">
        <button type="button" :disabled="busy || !backendReady" @click="createBackup">立即备份</button>
        <button type="button" :disabled="busy" @click="exportLogs">导出脱敏日志</button>
      </div>
      <div class="backup-list">
        <p v-if="!backups.length">尚无本地数据库备份。</p>
        <article v-for="backup in backups" :key="backup.name">
          <span><b>{{ formatDate(backup.created_at) }}</b><small>{{ formatBytes(backup.size) }}</small></span>
          <button type="button" :disabled="busy || interactionBusy" @click="restoreBackup(backup.name)">
            {{ restoreArmedName === backup.name ? '确认恢复' : '恢复' }}
          </button>
        </article>
      </div>
    </section>

    <section class="diagnostic-block event-block">
      <header><span>最近事件</span><small>REDACTED LOG</small></header>
      <p v-if="!snapshot.events?.length">本次运行尚无诊断事件。</p>
      <article v-for="event in [...(snapshot.events || [])].reverse().slice(0, 18)" :key="`${event.at}-${event.service}-${event.message}`">
        <span>{{ event.service }}</span>
        <small>{{ formatTime(event.at) }}</small>
        <p>{{ event.message }}</p>
      </article>
    </section>

    <p class="diagnostic-message" :class="{ error: messageError }">{{ message }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({ backendReady: Boolean, interactionBusy: Boolean })
const emit = defineEmits(['database-restored'])

const snapshot = ref({ app: {}, runtime: {}, events: [], safeMode: false })
const updateState = ref({ status: 'idle', progress: 0, message: '', currentVersion: '' })
const backups = ref([])
const safeMode = ref(false)
const busy = ref(false)
const message = ref('')
const messageError = ref(false)
const installArmed = ref(false)
const restoreArmedName = ref(null)
let removeUpdateListener

const backendDiagnostics = computed(() => snapshot.value.runtime?.backend || null)
const uptimeLabel = computed(() => {
  const seconds = snapshot.value.app?.uptime_seconds || 0
  if (seconds < 60) return `${seconds} SEC`
  return `${Math.floor(seconds / 60)} MIN`
})

watch(() => props.backendReady, ready => {
  if (ready) refresh()
})

onMounted(async () => {
  removeUpdateListener = window.electronAPI.onUpdateStatus(state => { updateState.value = state })
  await refresh()
})

onUnmounted(() => removeUpdateListener?.())

async function refresh() {
  if (busy.value) return
  busy.value = true
  try {
    const [diagnostics, updates] = await Promise.all([
      window.electronAPI.getDiagnostics(),
      window.electronAPI.getUpdateState()
    ])
    snapshot.value = diagnostics
    safeMode.value = diagnostics.safeMode
    updateState.value = updates
    if (props.backendReady) await loadBackups()
    setMessage('')
  } catch (error) {
    setMessage(readError(error, '无法读取诊断状态'), true)
  } finally {
    busy.value = false
  }
}

async function loadBackups() {
  const result = await window.electronAPI.listDatabaseBackups()
  backups.value = result.backups || []
}

async function restartService(service) {
  await runAction(async () => {
    await window.electronAPI.restartRuntimeService(service)
    setMessage(`${service === 'backend' ? '后端' : '桌宠'}重启请求已发送`)
    window.setTimeout(refresh, 1600)
  }, '服务重启失败')
}

async function changeSafeMode() {
  await runAction(async () => {
    snapshot.value = await window.electronAPI.setSafeMode(safeMode.value)
    safeMode.value = snapshot.value.safeMode
    setMessage(safeMode.value ? '安全模式已启用' : '安全模式已关闭')
  }, '安全模式切换失败')
}

async function checkUpdates() {
  await runAction(async () => {
    updateState.value = await window.electronAPI.checkForUpdates()
  }, '更新检查失败')
}

async function downloadUpdate() {
  await runAction(async () => {
    updateState.value = await window.electronAPI.downloadUpdate()
  }, '更新下载失败')
}

async function installUpdate() {
  if (!installArmed.value) {
    installArmed.value = true
    setMessage('再次点击后应用将退出并安装更新')
    return
  }
  await runAction(() => window.electronAPI.installUpdate(), '无法启动更新安装')
}

async function createBackup() {
  await runAction(async () => {
    await window.electronAPI.createDatabaseBackup()
    await loadBackups()
    setMessage('数据库备份已创建')
  }, '数据库备份失败')
}

async function restoreBackup(filename) {
  if (restoreArmedName.value !== filename) {
    restoreArmedName.value = filename
    setMessage('再次点击将恢复该备份；系统会先保存当前数据库')
    return
  }
  await runAction(async () => {
    await window.electronAPI.restoreDatabaseBackup(filename)
    restoreArmedName.value = null
    await loadBackups()
    emit('database-restored')
    setMessage('数据库已恢复，并保留了恢复前备份')
  }, '数据库恢复失败')
}

async function exportLogs() {
  await runAction(async () => {
    const result = await window.electronAPI.exportDiagnostics()
    if (result.exported) setMessage('脱敏诊断日志已导出')
  }, '诊断日志导出失败')
}

async function runAction(operation, fallback) {
  if (busy.value) return
  busy.value = true
  try {
    await operation()
  } catch (error) {
    setMessage(readError(error, fallback), true)
  } finally {
    busy.value = false
  }
}

function statusLabel(status) {
  return ({ ready: 'READY', starting: 'START', checking: 'CHECK', error: 'ERROR', disabled: 'SAFE' })[status] || 'OFFLINE'
}

function formatBytes(value) {
  const bytes = Number(value) || 0
  if (!bytes) return '0 B'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

function formatTime(value) {
  return value ? new Date(value).toLocaleTimeString('zh-CN', { hour12: false }) : ''
}

function readError(error, fallback) {
  const text = String(error?.message || '')
  return text.split('Error: ').at(-1) || fallback
}

function setMessage(text, error = false) {
  message.value = text
  messageError.value = error
}
</script>

<style scoped>
.diagnostics-console { display: grid; gap: 12px; }
.diagnostics-head { display: flex; align-items: end; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,.24); }
.diagnostics-head span { display: grid; gap: 4px; }
.diagnostics-head small, .diagnostic-block > header small { color: rgba(255,255,255,.4); font: 9px/1 'Novecento Sans', sans-serif; letter-spacing: .13em; }
.diagnostics-head b { font-size: 18px; font-weight: 500; letter-spacing: .08em; }
button { min-height: 28px; padding: 0 9px; border: 1px solid rgba(255,255,255,.17); color: #fff; background: rgba(0,0,0,.24); font: inherit; cursor: pointer; transition: border-color .2s, background .2s, transform .15s; }
button:hover:not(:disabled) { border-color: rgba(255,255,255,.62); background: rgba(255,255,255,.07); }
button:active:not(:disabled) { transform: translateY(1px); }
button:disabled { opacity: .27; cursor: default; }
button:focus-visible, input:focus-visible { outline: 1px solid #fff; outline-offset: 2px; }
.diagnostic-block { display: grid; gap: 9px; padding: 11px; border-left: 1px solid rgba(255,255,255,.17); background: rgba(255,255,255,.025); }
.diagnostic-block > header { display: flex; align-items: baseline; justify-content: space-between; }
.diagnostic-block > header span { color: rgba(255,255,255,.72); font-size: 11px; }
.runtime-grid, .data-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin: 0; background: rgba(255,255,255,.1); }
.runtime-grid div, .data-grid div { display: grid; gap: 4px; padding: 8px; background: rgba(3,3,3,.9); }
dt { color: rgba(255,255,255,.38); font-size: 8px; }
dd { margin: 0; color: rgba(255,255,255,.78); font: 9px/1 'Novecento Sans', sans-serif; font-variant-numeric: tabular-nums; }
.diagnostic-actions { display: flex; justify-content: flex-end; gap: 6px; }
.safe-mode-setting { min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,.08); cursor: pointer; }
.safe-mode-setting span { display: grid; gap: 3px; }
.safe-mode-setting b { font-size: 10px; font-weight: 500; }
.safe-mode-setting small { color: rgba(255,255,255,.35); font-size: 8px; }
.safe-mode-setting input { width: 28px; accent-color: #fff; }
.update-state { display: flex; align-items: end; justify-content: space-between; }
.update-state span { display: grid; gap: 4px; }
.update-state b { font: 15px/1 'Novecento Sans', sans-serif; font-variant-numeric: tabular-nums; }
.update-state small { color: rgba(255,255,255,.4); font-size: 9px; }
.update-state output { color: rgba(255,255,255,.65); font: 10px/1 'Novecento Sans', sans-serif; }
.update-progress { height: 2px; background: rgba(255,255,255,.1); }
.update-progress i { display: block; height: 100%; background: #fff; box-shadow: 0 0 8px rgba(255,255,255,.55); transition: width .2s linear; }
.backup-list { display: grid; max-height: 145px; overflow: auto; border-top: 1px solid rgba(255,255,255,.08); }
.backup-list > p { margin: 0; padding: 14px 0; color: rgba(255,255,255,.35); font-size: 9px; }
.backup-list article { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,.06); }
.backup-list article span { min-width: 0; display: grid; gap: 3px; }
.backup-list article b { overflow: hidden; font-size: 9px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.backup-list article small { color: rgba(255,255,255,.34); font-size: 8px; }
.backup-list article button { min-height: 24px; font-size: 9px; }
.event-block > p { color: rgba(255,255,255,.35); font-size: 9px; }
.event-block article { display: grid; grid-template-columns: auto 1fr; gap: 3px 8px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,.06); }
.event-block article > span { color: rgba(255,255,255,.64); font: 8px/1 'Novecento Sans', sans-serif; text-transform: uppercase; }
.event-block article > small { color: rgba(255,255,255,.28); font-size: 8px; text-align: right; }
.event-block article > p { grid-column: 1 / -1; margin: 0; color: rgba(255,255,255,.46); font: 8px/1.45 var(--font-mono); word-break: break-word; }
.diagnostic-message { min-height: 16px; margin: 0; color: rgba(255,255,255,.55); font-size: 10px; }
.diagnostic-message.error { color: #fff; text-decoration: underline dotted; text-underline-offset: 3px; }
</style>
