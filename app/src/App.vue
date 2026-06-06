<template>
  <div class="app-root" :class="{ 'mode-pet': mode === 'pet', 'mode-chat': mode === 'chat' }">
    <PetMode v-if="mode === 'pet'" @open-chat="openChat" />
    <ChatMode
      v-else
      :messages="messages"
      :is-typing="isTyping"
      :current-text="currentDisplayText"
      :touch-text="touchText"
      :touch-active="touchActive"
      @send="handleSend"
      @close="closeToSpeaker"
      @minimize="minimizeWindow"
      @test-voice="() => playFile('问候.wav')"
      @touch-sprite="handleSpriteTouch"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import PetMode from './components/PetMode.vue'
import ChatMode from './components/ChatMode.vue'
import { sendMessage } from './api/chat.js'
import { playVoice, playFile } from './api/voice.js'

// 全局点击波纹
function spawnRipple(e) {
  const el = document.createElement('div')
  el.className = 'click-ripple'
  el.style.left = e.clientX + 'px'
  el.style.top  = e.clientY + 'px'
  document.body.appendChild(el)
  el.addEventListener('animationend', () => el.remove())
}
onMounted(() => window.addEventListener('mousedown', spawnRipple))
onUnmounted(() => window.removeEventListener('mousedown', spawnRipple))

// 台词文案中 {@nickname} 的替换，读自设置
function getDoctorName() {
  const s = JSON.parse(localStorage.getItem('kaltsit_settings') || 'null')
  return s?.doctorName || '真理'
}

const mode   = ref('chat')
const messages = ref([
  { role: 'assistant', text: '不必过分在意我的状态，我会尽快适应生理机能的些许变化，这不会妨碍我的工作。从现在开始，还是由我来担任你的全科医生。' }
])
const isTyping           = ref(false)
const currentDisplayText = ref('')
const touchText          = ref('')
const touchActive        = ref(false)

// 触摸立绘：台词与语音严格一一对应（思衡托语音库）
const TOUCH_PAIRS = [
  { file: '戳一下.wav',          text: '不必频繁确认我的状态，这副躯体与常人无异。' },
  { file: '交谈1.wav',           text: '石棺的核心装置正维系着我的生命，短时间内我还无法脱离它而行动。谨慎对待自己的生命状态，对我来说也算是从未有过的体验。许多事物我都要重新熟悉。也许这一次，我还是会需要你的指引。' },
  { file: '交谈2.wav',           text: '你们在最危急的时候带领罗德岛找到了航向，阿米娅无疑已经是成熟的领袖，我也从未怀疑过可露希尔的才能与你的决策。罗德岛不会因为离开谁就无法前行，失去的一切同样造就了现在的罗德岛。' },
  { file: '交谈3.wav',           text: '我很高兴Mon3tr可以用这种方式融入罗德岛，虽然没有同类，但所幸还有许多人将她视作同伴。她不会忘记与我一同承担过的使命，你可以完全信任她。此后的时间里，她会陪伴你更久。' },
  { file: '问候.wav',            text: '博士，我在。' },
  { file: '信赖触摸.wav',        text: '如果你的确很在意的话，我现在很好。' },
  { file: '信赖提升后交谈1.wav', text: '那些离别无法释怀亦无法挽回，我也不曾想过还能得到另一次的生命，我很庆幸，也很感激。我只是像做了一场梦，而你们一定经历了煎熬的等待。抱歉......你说得对，这样的离别并不公平。' },
  { file: '信赖提升后交谈2.wav', text: '我们的交谈不会再受到限制，对现在的你来说我已经没有什么秘密。我乐意与你分享过往万年的见闻，可是那些思绪与感受恐怕难以用言语传达。好，在这些记忆淡去之前，我会尽可能讲给你听。' },
  { file: '信赖提升后交谈3.wav', text: '我永远不会忘记有人曾与我谈论过生命与爱，我终于可以在这副躯体有限的时间里做出回应。我会耐心接受时间的磋磨，也会将立下的誓言履行下去，直到下一次，真正的死亡使我们分离。' },
]

let lastTouchIdx = -1

function handleSpriteTouch() {
  // 排除上一次，随机选一对
  const pool = TOUCH_PAIRS.map((_, i) => i).filter(i => i !== lastTouchIdx)
  const idx  = pool[Math.floor(Math.random() * pool.length)]
  lastTouchIdx = idx

  const pair = TOUCH_PAIRS[idx]
  const name = getDoctorName()

  touchText.value   = pair.text.replace(/博士/g, name)
  touchActive.value = true
  playFile(pair.file)
}

onMounted(() => {
  setTimeout(() => playFile('任命助理.wav'), 800)
  // 监听主进程右键菜单的"展开对话"
  window.electronAPI?.onOpenChat(() => openChat())
})

function openChat() {
  mode.value = 'chat'
  window.electronAPI?.setMode('chat')
}

function closeToSpeaker() {
  mode.value = 'pet'
  window.electronAPI?.setMode('pet')
}

function minimizeWindow() {
  window.electronAPI?.minimizeWindow()
}

async function handleSend(text) {
  if (!text.trim() || isTyping.value) return
  touchActive.value = false

  const name = getDoctorName()
  messages.value.push({ role: 'user', text })
  isTyping.value = true
  currentDisplayText.value = ''

  try {
    const raw = await sendMessage(messages.value)
    // 替换回复中的称呼占位符
    const reply = raw.replace(/Dr\.\{@nickname\}/g, name).replace(/\{@nickname\}/g, name)
    await typewriterDisplay(reply)
    messages.value.push({ role: 'assistant', text: reply })
    playVoice(reply)
  } catch (e) {
    const fallback = '......'
    currentDisplayText.value = fallback
    messages.value.push({ role: 'assistant', text: fallback })
    playFile('闲置.wav')
  } finally {
    isTyping.value = false
    currentDisplayText.value = ''
  }
}

async function typewriterDisplay(text) {
  currentDisplayText.value = ''
  for (const char of text) {
    currentDisplayText.value += char
    await sleep(28)
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms))
}
</script>

<style scoped>
.app-root {
  width: 500px;
  height: 700px;
  background: transparent;
  position: relative;
  overflow: hidden;
  contain: strict;
}
</style>
