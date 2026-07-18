import client from './client.js'

const VOICE_FOLDER = '凯尔希思衡托'
const BASE = 'http://127.0.0.1:8765/voice'
const API_BASE = 'http://127.0.0.1:8765'

// AI 回复关键词 → 语音匹配（基于实际台词内容）
const TRIGGER_MAP = [
  { keywords: ['生日'],                   files: ['生日.wav'] },
  { keywords: ['新年', '祝福'],            files: ['新年祝福.wav'] },
  { keywords: ['出发', '减少伤亡'],         files: ['行动出发.wav', '行动开始.wav'] },
  { keywords: ['治愈', '修复', '治疗'],     files: ['作战中4.wav', '作战中2.wav'] },
  { keywords: ['撤离', '善后'],            files: ['行动失败.wav'] },
  { keywords: ['石棺', '生命', '指引'],     files: ['交谈1.wav'] },
  { keywords: ['罗德岛', '领袖', '航向'],   files: ['交谈2.wav'] },
  { keywords: ['Mon3tr', 'Mon3TR', '信任她'], files: ['交谈3.wav'] },
  { keywords: ['离别', '等待', '公平'],     files: ['信赖提升后交谈1.wav'] },
  { keywords: ['秘密', '万年', '见闻'],     files: ['信赖提升后交谈2.wav'] },
  { keywords: ['誓言', '死亡', '爱'],       files: ['信赖提升后交谈3.wav'] },
  { keywords: ['迷茫', '使命', '承诺'],     files: ['晋升后交谈2.wav'] },
  { keywords: ['泰拉', '未来', '希望'],     files: ['完成高难行动.wav'] },
  { keywords: ['危险', '孤独', '旅程'],     files: ['生日.wav'] },
]

// 无关键词命中时随机选对话语音
const CHAT_VOICES = [
  '问候.wav', '交谈1.wav', '交谈2.wav', '交谈3.wav',
  '信赖触摸.wav',
  '信赖提升后交谈1.wav', '信赖提升后交谈2.wav', '信赖提升后交谈3.wav',
  '晋升后交谈1.wav', '晋升后交谈2.wav',
  '任命助理.wav', '任命队长.wav',
]

let currentAudio = null
let lastPlayed = ''
let _volume = 0.85
let outputMode = localStorage.getItem('kaltsit_voice_output') || 'recorded'
let audioContext = null
let animationFrame = null
let currentSource = null
let currentAnalyser = null

export function setVolume(v) {
  _volume = Math.max(0, Math.min(1, v))
  if (currentAudio) currentAudio.volume = _volume
}

export function setVoiceOutputMode(mode) {
  outputMode = ['text', 'recorded', 'local-model'].includes(mode) ? mode : 'recorded'
  localStorage.setItem('kaltsit_voice_output', outputMode)
  if (outputMode === 'text') stopVoice()
}

export function getVoiceOutputMode() {
  return outputMode
}

/**
 * AI 回复后播放：优先关键词匹配，否则随机
 */
export function playVoice(text) {
  if (outputMode === 'text') return
  const matched = TRIGGER_MAP.find(t =>
    t.keywords.some(kw => text.includes(kw))
  )
  let filename
  if (matched) {
    filename = matched.files[Math.floor(Math.random() * matched.files.length)]
  } else {
    const candidates = CHAT_VOICES.filter(f => f !== lastPlayed)
    filename = candidates[Math.floor(Math.random() * candidates.length)]
  }
  lastPlayed = filename
  playFile(filename)
}

export function playFile(filename) {
  stopVoice()
  const url = `${BASE}/${encodeURIComponent(VOICE_FOLDER)}/${encodeURIComponent(filename)}`
  const audio = new Audio()
  audio.crossOrigin = 'anonymous'
  audio.src = url
  audio.volume = _volume
  audio.addEventListener('ended', stopVoice, { once: true })
  audio.play()
    .then(() => startLipSync(audio))
    .catch(e => console.warn('[voice] 播放失败:', url, e.message))
  currentAudio = audio
}

export function stopVoice() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.removeAttribute('src')
    currentAudio.load()
    currentAudio = null
  }
  if (animationFrame) cancelAnimationFrame(animationFrame)
  animationFrame = null
  currentSource?.disconnect()
  currentAnalyser?.disconnect()
  currentSource = null
  currentAnalyser = null
  window.electronAPI?.setPetLipSync?.(0)
}

export async function getVoiceRecognitionStatus() {
  const response = await client.get(`${API_BASE}/voice-recognition/status`)
  return response.data
}

export async function reloadVoiceRecognitionModel() {
  const response = await client.post(`${API_BASE}/voice-recognition/model/reload`, null, { timeout: 180000 })
  return response.data
}

export async function downloadVoiceRecognitionModel() {
  const response = await client.post(`${API_BASE}/voice-recognition/model/download`, null, { timeout: 900000 })
  return response.data
}

export async function transcribeRecording(blob, language = 'auto') {
  const audioBase64 = await blobToBase64(blob)
  const response = await client.post(`${API_BASE}/voice-recognition/transcribe`, {
    audio_base64: audioBase64,
    language
  }, { timeout: 180000 })
  return response.data
}

function startLipSync(audio) {
  audioContext ||= new AudioContext()
  const source = audioContext.createMediaElementSource(audio)
  const analyser = audioContext.createAnalyser()
  analyser.fftSize = 256
  analyser.smoothingTimeConstant = 0.68
  source.connect(analyser)
  analyser.connect(audioContext.destination)
  currentSource = source
  currentAnalyser = analyser
  const levels = new Uint8Array(analyser.frequencyBinCount)
  let lastSent = 0

  const update = timestamp => {
    if (audio !== currentAudio || audio.paused || audio.ended) return
    analyser.getByteFrequencyData(levels)
    const average = levels.reduce((sum, value) => sum + value, 0) / levels.length
    if (timestamp - lastSent >= 50) {
      window.electronAPI?.setPetLipSync?.(Math.max(0, Math.min(1, average / 92)))
      lastSent = timestamp
    }
    animationFrame = requestAnimationFrame(update)
  }
  animationFrame = requestAnimationFrame(update)
}

async function blobToBase64(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  const chunkSize = 0x8000
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize))
  }
  return btoa(binary)
}
