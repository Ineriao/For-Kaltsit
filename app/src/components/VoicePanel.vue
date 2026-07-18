<template>
  <div class="voice-panel">
    <section class="terminal-section">
      <header>
        <span>输入识别</span>
        <small>LOCAL ASR / VAD</small>
      </header>
      <div class="engine-state">
        <span>
          <b>SENSEVOICE SMALL INT8</b>
          <small>{{ status.ready ? `READY · ${status.source?.toUpperCase()}` : 'MODEL NOT INSTALLED' }}</small>
        </span>
        <i :class="{ ready: status.ready }" />
      </div>
      <div class="action-grid">
        <button type="button" :disabled="busy" @click="downloadModel">下载模型</button>
        <button type="button" :disabled="busy" @click="importModel">手动导入</button>
        <button type="button" :disabled="busy || !status.ready" @click="reloadModel">重新加载</button>
      </div>
      <p class="model-note">下载约 156 MB / 解压约 228 MB · 中文 / EN / 日本語 / 한국어 / 粤语</p>
    </section>

    <section class="terminal-section">
      <header>
        <span>识别行为</span>
        <small>VOICE ACTIVITY</small>
      </header>
      <button type="button" class="toggle-row" :class="{ active: autoSend }" @click="toggleAutoSend">
        <span>
          <b>静音后自动发送</b>
          <small>检测到约 0.95 秒静音后结束录音并发送</small>
        </span>
        <i />
      </button>
      <div class="vad-metrics">
        <span><small>采样</small><b>16 KHZ</b></span>
        <span><small>最长</small><b>30 SEC</b></span>
        <span><small>处理</small><b>LOCAL</b></span>
      </div>
    </section>

    <section class="terminal-section">
      <header>
        <span>回复声音</span>
        <small>TTS OUTPUT</small>
      </header>
      <div class="mode-grid">
        <button type="button" :class="{ active: outputMode === 'text' }" @click="selectOutput('text')">
          <b>纯文本</b><small>不播放语音</small>
        </button>
        <button type="button" :class="{ active: outputMode === 'recorded' }" @click="selectOutput('recorded')">
          <b>现有录音</b><small>关键词匹配</small>
        </button>
        <button type="button" :class="{ active: outputMode === 'local-model' }" disabled>
          <b>音色模型</b><small>训练后启用</small>
        </button>
      </div>
      <p class="model-note">播放可被新录音立即打断，音量强度实时驱动 Spine 嘴型。</p>
    </section>

    <p v-if="message" class="panel-message">{{ message }}</p>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import {
  downloadVoiceRecognitionModel,
  getVoiceOutputMode,
  getVoiceRecognitionStatus,
  reloadVoiceRecognitionModel,
  setVoiceOutputMode
} from '../api/voice.js'

const props = defineProps({ backendReady: Boolean })
const emit = defineEmits(['status-change'])

const status = ref({ ready: false, source: null })
const busy = ref(false)
const message = ref('')
const outputMode = ref(getVoiceOutputMode())
const autoSend = ref(localStorage.getItem('kaltsit_voice_auto_send') !== 'false')

watch(() => props.backendReady, ready => {
  if (ready) loadStatus()
})

onMounted(() => {
  if (props.backendReady) loadStatus()
})

async function loadStatus() {
  try {
    status.value = await getVoiceRecognitionStatus()
    emit('status-change', status.value)
  } catch (error) {
    message.value = getRequestError(error, '语音识别状态读取失败')
  }
}

async function downloadModel() {
  busy.value = true
  message.value = '正在下载约 156 MB 的本地识别模型。'
  try {
    if (window.electronAPI?.downloadVoiceRecognitionModel) {
      await window.electronAPI.downloadVoiceRecognitionModel()
      status.value = await reloadVoiceRecognitionModel()
    } else {
      status.value = await downloadVoiceRecognitionModel()
    }
    emit('status-change', status.value)
    message.value = '本地语音识别模型已就绪。'
  } catch (error) {
    message.value = getRequestError(error, '语音识别模型下载失败')
  } finally {
    busy.value = false
  }
}

async function importModel() {
  busy.value = true
  message.value = ''
  try {
    const result = await window.electronAPI.importVoiceRecognitionModel()
    if (result?.canceled) return
    if (!result?.imported) throw new Error(result?.error || '模型导入失败')
    status.value = await reloadVoiceRecognitionModel()
    emit('status-change', status.value)
    message.value = '手动导入的识别模型已加载。'
  } catch (error) {
    message.value = getRequestError(error, '语音识别模型导入失败')
  } finally {
    busy.value = false
  }
}

async function reloadModel() {
  busy.value = true
  try {
    status.value = await reloadVoiceRecognitionModel()
    emit('status-change', status.value)
    message.value = '语音识别模型已重新加载。'
  } catch (error) {
    message.value = getRequestError(error, '语音识别模型加载失败')
  } finally {
    busy.value = false
  }
}

function selectOutput(mode) {
  outputMode.value = mode
  setVoiceOutputMode(mode)
}

function toggleAutoSend() {
  autoSend.value = !autoSend.value
  localStorage.setItem('kaltsit_voice_auto_send', String(autoSend.value))
}

function getRequestError(error, fallback) {
  return error.response?.data?.detail || error.message || fallback
}
</script>

<style scoped>
.voice-panel { display: grid; gap: 11px; }
.terminal-section { padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.1); }
.terminal-section:first-child { padding-top: 0; border-top: 0; }
.terminal-section > header { display: flex; justify-content: space-between; margin-bottom: 7px; }
.terminal-section > header span { color: rgba(255, 255, 255, 0.76); font-size: 8px; }
.terminal-section > header small { color: rgba(255, 255, 255, 0.28); font: 5.8px var(--font-mono); }
.engine-state { display: flex; align-items: center; justify-content: space-between; padding: 8px; border-left: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.18); }
.engine-state b, .engine-state small { display: block; }
.engine-state b { color: rgba(255, 255, 255, 0.72); font: 7px 'Novecento Sans', sans-serif; letter-spacing: 0.08em; }
.engine-state small { margin-top: 4px; color: rgba(255, 255, 255, 0.26); font: 5.8px var(--font-mono); }
.engine-state i { width: 5px; height: 5px; border: 1px solid rgba(255, 255, 255, 0.24); transform: rotate(45deg); }
.engine-state i.ready { background: white; border-color: white; box-shadow: 0 0 8px rgba(255, 255, 255, 0.7); }
button { border: 1px solid rgba(255, 255, 255, 0.11); color: rgba(255, 255, 255, 0.48); background: rgba(255, 255, 255, 0.018); font-size: 6.5px; }
button:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.3); color: white; background: rgba(255, 255, 255, 0.05); }
button:disabled { opacity: 0.28; }
.action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 5px; }
.action-grid button { min-height: 26px; }
.model-note { margin: 6px 0 0; color: rgba(255, 255, 255, 0.22); font: 5.6px/1.5 var(--font-mono); }
.toggle-row { width: 100%; min-height: 47px; display: flex; align-items: center; justify-content: space-between; padding: 0 9px; text-align: left; }
.toggle-row b, .toggle-row small { display: block; }
.toggle-row b { color: rgba(255, 255, 255, 0.72); font-size: 7.5px; font-weight: 520; }
.toggle-row small { margin-top: 4px; color: rgba(255, 255, 255, 0.26); font-size: 6px; }
.toggle-row > i { width: 18px; height: 7px; border: 1px solid currentColor; }
.toggle-row.active > i { background: white; box-shadow: 0 0 7px rgba(255, 255, 255, 0.55); }
.vad-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin-top: 5px; background: rgba(255, 255, 255, 0.08); }
.vad-metrics > span { padding: 7px; background: rgba(0, 0, 0, 0.62); }
.vad-metrics small, .vad-metrics b { display: block; }
.vad-metrics small { color: rgba(255, 255, 255, 0.24); font-size: 5.5px; }
.vad-metrics b { margin-top: 4px; color: rgba(255, 255, 255, 0.62); font: 6px 'Novecento Sans', sans-serif; }
.mode-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.mode-grid button { min-height: 49px; }
.mode-grid b, .mode-grid small { display: block; }
.mode-grid b { font-size: 7px; font-weight: 520; }
.mode-grid small { margin-top: 4px; color: rgba(255, 255, 255, 0.24); font-size: 5.5px; }
.mode-grid button.active { color: white; border-color: rgba(255, 255, 255, 0.42); box-shadow: inset 0 -1px 0 white; }
.panel-message { margin: 0; padding: 7px 8px; border-left: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.5); background: rgba(0, 0, 0, 0.16); font-size: 6.5px; line-height: 1.5; }
</style>
