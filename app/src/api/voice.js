const VOICE_FOLDER = '凯尔希思衡托'
const BASE = 'http://127.0.0.1:8765/voice'

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

export function setVolume(v) {
  _volume = Math.max(0, Math.min(1, v))
  if (currentAudio) currentAudio.volume = _volume
}

/**
 * AI 回复后播放：优先关键词匹配，否则随机
 */
export function playVoice(text) {
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
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
  const url = `${BASE}/${encodeURIComponent(VOICE_FOLDER)}/${encodeURIComponent(filename)}`
  const audio = new Audio(url)
  audio.volume = _volume
  audio.play().catch(e => console.warn('[voice] 播放失败:', url, e.message))
  currentAudio = audio
}
