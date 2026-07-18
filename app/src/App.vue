<template>
  <div class="app-root">
    <SetupWizard
      v-if="setupVisible"
      @complete="handleSetupComplete"
    />
    <ChatMode
      v-else
      :messages="messages"
      :is-typing="isTyping"
      :is-responding="isResponding"
      :is-busy="isResponding || isTyping"
      :current-text="currentDisplayText"
      :page-index="replyPageIndex"
      :page-count="replyPages.length || 1"
      :touch-text="touchText"
      :touch-active="touchActive"
      :runtime-status="runtimeStatus"
      :error-text="errorText"
      :sessions="sessions"
      :current-session-id="currentSessionId"
      @send="handleSend"
      @next-page="handleNextPage"
      @previous-page="handlePreviousPage"
      @close="closeToSpeaker"
      @minimize="minimizeWindow"
      @test-voice="() => playFile('问候.wav')"
      @touch-sprite="handleSpriteTouch"
      @create-session="createNewSession"
      @select-session="selectSession"
      @rename-session="handleRenameSession"
      @delete-session="handleDeleteSession"
      @database-restored="handleDatabaseRestored"
    />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import ChatMode from './components/ChatMode.vue'
import SetupWizard from './components/SetupWizard.vue'
import {
  createSession,
  deleteSession,
  getHealth,
  getSessionMessages,
  getSessions,
  renameSession,
  sendMessage
} from './api/chat.js'
import { playFile, playVoice } from './api/voice.js'

const INITIAL_GREETING = '不必过分在意我的状态，我会尽快适应生理机能的些许变化，这不会妨碍我的工作。从现在开始，还是由我来担任你的全科医生。'
const messages = ref([{ role: 'assistant', text: INITIAL_GREETING }])
const sessions = ref([])
const currentSessionId = ref(null)
const isTyping = ref(false)
const isResponding = ref(false)
const currentDisplayText = ref('')
const replyPages = ref([])
const replyPageIndex = ref(0)
const touchText = ref('')
const touchActive = ref(false)
const runtimeStatus = ref({ backend: 'checking', pet: 'checking', aiConfigured: null })
const errorText = ref('')
const setupVisible = ref(false)

const TOUCH_PAIRS = [
  { file: '戳一下.wav', text: '不必频繁确认我的状态，这副躯体与常人无异。' },
  { file: '交谈1.wav', text: '石棺的核心装置正维系着我的生命，短时间内我还无法脱离它而行动。谨慎对待自己的生命状态，对我来说也算是从未有过的体验。许多事物我都要重新熟悉。也许这一次，我还是会需要你的指引。' },
  { file: '交谈2.wav', text: '你们在最危急的时候带领罗德岛找到了航向，阿米娅无疑已经是成熟的领袖，我也从未怀疑过可露希尔的才能与你的决策。罗德岛不会因为离开谁就无法前行，失去的一切同样造就了现在的罗德岛。' },
  { file: '交谈3.wav', text: '我很高兴Mon3tr可以用这种方式融入罗德岛，虽然没有同类，但所幸还有许多人将她视作同伴。她不会忘记与我一同承担过的使命，你可以完全信任她。此后的时间里，她会陪伴你更久。' },
  { file: '问候.wav', text: '博士，我在。' },
  { file: '信赖触摸.wav', text: '如果你的确很在意的话，我现在很好。' },
  { file: '信赖提升后交谈1.wav', text: '那些离别无法释怀亦无法挽回，我也不曾想过还能得到另一次的生命，我很庆幸，也很感激。我只是像做了一场梦，而你们一定经历了煎熬的等待。抱歉......你说得对，这样的离别并不公平。' },
  { file: '信赖提升后交谈2.wav', text: '我们的交谈不会再受到限制，对现在的你来说我已经没有什么秘密。我乐意与你分享过往万年的见闻，可是那些思绪与感受恐怕难以用言语传达。好，在这些记忆淡去之前，我会尽可能讲给你听。' },
  { file: '信赖提升后交谈3.wav', text: '我永远不会忘记有人曾与我谈论过生命与爱，我终于可以在这副躯体有限的时间里做出回应。我会耐心接受时间的磋磨，也会将立下的誓言履行下去，直到下一次，真正的死亡使我们分离。' }
]

let lastTouchIndex = -1
let removeRuntimeListener
let removeOpenChatListener
let removeSetupListener
let removeSetupCompleteListener
let healthTimer
let typingGeneration = 0
let pendingReply = ''
let pendingSources = []
let replyCommitted = true
let sessionsInitializing = false
const revealedPages = new Set()

initializeSubtitle()

onMounted(async () => {
  if (window.electronAPI?.getSetupState) {
    const setup = await window.electronAPI.getSetupState()
    setupVisible.value = !setup.complete
  }
  removeSetupListener = window.electronAPI?.onShowSetup(() => {
    setupVisible.value = true
  })
  removeSetupCompleteListener = window.electronAPI?.onSetupComplete(handleSetupComplete)
  removeOpenChatListener = window.electronAPI?.onOpenChat(handleOpenChat)
  removeRuntimeListener = window.electronAPI?.onRuntimeStatus(status => {
    runtimeStatus.value = { ...runtimeStatus.value, ...status }
    if (status.backend === 'ready') initializeSessions()
  })

  if (window.electronAPI?.getRuntimeStatus) {
    runtimeStatus.value = await window.electronAPI.getRuntimeStatus()
    if (runtimeStatus.value.backend === 'ready') await initializeSessions()
  } else {
    await checkBackendHealth()
    healthTimer = window.setInterval(checkBackendHealth, 5000)
  }
})

onUnmounted(() => {
  typingGeneration += 1
  removeRuntimeListener?.()
  removeOpenChatListener?.()
  removeSetupListener?.()
  removeSetupCompleteListener?.()
  window.clearInterval(healthTimer)
})

function initializeSubtitle() {
  replyPages.value = paginateReply(messages.value[0].text)
  replyPageIndex.value = 0
  currentDisplayText.value = replyPages.value[0] || ''
  revealedPages.add(0)
}

function getDoctorName() {
  try {
    const settings = JSON.parse(localStorage.getItem('kaltsit_settings') || 'null')
    return settings?.doctorName || '博士'
  } catch (error) {
    return '博士'
  }
}

function handleSpriteTouch() {
  if (isResponding.value) return
  const pool = TOUCH_PAIRS.map((_, index) => index).filter(index => index !== lastTouchIndex)
  const index = pool[Math.floor(Math.random() * pool.length)]
  lastTouchIndex = index
  const pair = TOUCH_PAIRS[index]
  const fullTouchText = pair.text.replace(/博士/g, getDoctorName())
  typingGeneration += 1
  isTyping.value = false
  replyPages.value = paginateReply(fullTouchText)
  replyPageIndex.value = 0
  touchText.value = replyPages.value[0] || fullTouchText
  touchActive.value = true
  window.electronAPI?.triggerPetAction('TOUCH')
  playFile(pair.file)
}

function handleOpenChat() {
  errorText.value = ''
  window.setTimeout(() => playFile('任命助理.wav'), 450)
}

function handleSetupComplete() {
  setupVisible.value = false
  errorText.value = ''
}

async function checkBackendHealth() {
  try {
    const health = await getHealth()
    runtimeStatus.value = {
      ...runtimeStatus.value,
      backend: 'ready',
      aiConfigured: Boolean(health.configured)
    }
    await initializeSessions()
  } catch (error) {
    runtimeStatus.value = { ...runtimeStatus.value, backend: 'error' }
  }
}

function closeToSpeaker() {
  window.electronAPI?.hideWindow()
}

function minimizeWindow() {
  window.electronAPI?.minimizeWindow()
}

async function handleSend(text, toolContext = null) {
  if (!text.trim() || isResponding.value) return
  if (!currentSessionId.value) {
    try {
      await createNewSession()
    } catch (error) {
      errorText.value = '无法建立本地会话，请检查后端状态。'
      return
    }
  }

  resetReplyPresentation()
  touchActive.value = false
  errorText.value = ''
  messages.value.push({ role: 'user', text })
  isResponding.value = true

  try {
    const response = await sendMessage(messages.value, currentSessionId.value, toolContext)
    pendingReply = response.reply
      .replace(/Dr\.\{@nickname\}/g, getDoctorName())
      .replace(/\{@nickname\}/g, getDoctorName())
    pendingSources = response.sources || []
    if (response.behavior) window.electronAPI?.triggerPetBehavior(response.behavior)
    else window.electronAPI?.triggerPetAction(response.action || 'RELAX')
    replyPages.value = paginateReply(pendingReply)
    replyPageIndex.value = 0
    replyCommitted = false
    revealedPages.clear()
    await typeCurrentPage()
    await refreshSessions()
  } catch (error) {
    const fallback = '本地通信暂时中断。待服务恢复后，再继续。'
    pendingReply = fallback
    pendingSources = []
    replyPages.value = [fallback]
    replyPageIndex.value = 0
    currentDisplayText.value = fallback
    revealedPages.add(0)
    replyCommitted = false
    commitReply(false)
    errorText.value = getChatErrorMessage(error)
    runtimeStatus.value = { ...runtimeStatus.value, backend: 'error' }
    playFile('闲置.wav')
    await refreshSessions().catch(() => {})
  }
}

async function initializeSessions() {
  if (sessionsInitializing || setupVisible.value || runtimeStatus.value.backend !== 'ready') return
  sessionsInitializing = true
  try {
    await refreshSessions()
    if (!sessions.value.length) {
      await createNewSession()
      return
    }

    const savedSessionId = localStorage.getItem('kaltsit_current_session')
    const target = sessions.value.find(session => session.id === savedSessionId) || sessions.value[0]
    if (currentSessionId.value !== target.id) await selectSession(target.id)
  } catch (error) {
    console.error('[sessions] 初始化失败:', error)
  } finally {
    sessionsInitializing = false
  }
}

async function refreshSessions() {
  sessions.value = await getSessions()
}

async function createNewSession() {
  if (isResponding.value) return
  const session = await createSession(INITIAL_GREETING)
  await refreshSessions()
  currentSessionId.value = session.id
  localStorage.setItem('kaltsit_current_session', session.id)
  setConversationMessages([{ role: 'assistant', text: INITIAL_GREETING }])
}

async function selectSession(sessionId) {
  if (!sessionId || isResponding.value || sessionId === currentSessionId.value) return
  const storedMessages = await getSessionMessages(sessionId)
  currentSessionId.value = sessionId
  localStorage.setItem('kaltsit_current_session', sessionId)
  setConversationMessages(storedMessages.length
    ? storedMessages
    : [{ role: 'assistant', text: INITIAL_GREETING }])
}

async function handleRenameSession({ id, title }) {
  if (!id || !title?.trim()) return
  await renameSession(id, title.trim())
  await refreshSessions()
}

async function handleDeleteSession(sessionId) {
  if (!sessionId || isResponding.value) return
  await deleteSession(sessionId)
  await refreshSessions()
  if (sessionId !== currentSessionId.value) return

  currentSessionId.value = null
  localStorage.removeItem('kaltsit_current_session')
  if (sessions.value.length) await selectSession(sessions.value[0].id)
  else await createNewSession()
}

async function handleDatabaseRestored() {
  currentSessionId.value = null
  sessions.value = []
  localStorage.removeItem('kaltsit_current_session')
  setConversationMessages([{ role: 'assistant', text: INITIAL_GREETING }])
  await initializeSessions()
}

function setConversationMessages(nextMessages) {
  resetReplyPresentation()
  touchActive.value = false
  touchText.value = ''
  messages.value = nextMessages.map(message => ({
    role: message.role,
    text: message.text,
    sources: message.sources || []
  }))

  const lastMessage = messages.value.at(-1)
  if (lastMessage?.role === 'assistant') {
    replyPages.value = paginateReply(lastMessage.text)
    replyPageIndex.value = 0
    currentDisplayText.value = replyPages.value[0] || ''
    revealedPages.add(0)
  }
}

function handleNextPage() {
  if (!replyPages.value.length) return

  if (touchActive.value) {
    if (replyPageIndex.value >= replyPages.value.length - 1) return
    replyPageIndex.value += 1
    touchText.value = replyPages.value[replyPageIndex.value]
    return
  }

  if (isTyping.value) {
    typingGeneration += 1
    currentDisplayText.value = replyPages.value[replyPageIndex.value]
    revealedPages.add(replyPageIndex.value)
    isTyping.value = false
    if (replyPageIndex.value === replyPages.value.length - 1) commitReply(true)
    return
  }

  if (replyPageIndex.value >= replyPages.value.length - 1) return
  replyPageIndex.value += 1

  if (revealedPages.has(replyPageIndex.value)) {
    currentDisplayText.value = replyPages.value[replyPageIndex.value]
    return
  }

  typeCurrentPage()
}

function handlePreviousPage() {
  if (replyPageIndex.value <= 0) return
  if (touchActive.value) {
    replyPageIndex.value -= 1
    touchText.value = replyPages.value[replyPageIndex.value]
    return
  }
  typingGeneration += 1
  isTyping.value = false
  replyPageIndex.value -= 1
  currentDisplayText.value = replyPages.value[replyPageIndex.value]
}

async function typeCurrentPage() {
  const pageIndex = replyPageIndex.value
  const pageText = replyPages.value[pageIndex] || ''
  const generation = ++typingGeneration
  currentDisplayText.value = ''
  isTyping.value = true

  for (const character of pageText) {
    if (generation !== typingGeneration || pageIndex !== replyPageIndex.value) return
    currentDisplayText.value += character
    await sleep(28)
  }

  if (generation !== typingGeneration) return
  revealedPages.add(pageIndex)
  isTyping.value = false

  if (pageIndex === replyPages.value.length - 1) commitReply(true)
}

function commitReply(playReplyVoice) {
  if (replyCommitted) return
  replyCommitted = true
  messages.value.push({ role: 'assistant', text: pendingReply, sources: pendingSources })
  isResponding.value = false
  if (playReplyVoice) playVoice(pendingReply)
}

function resetReplyPresentation() {
  typingGeneration += 1
  pendingReply = ''
  pendingSources = []
  replyCommitted = true
  replyPages.value = []
  replyPageIndex.value = 0
  currentDisplayText.value = ''
  revealedPages.clear()
  isTyping.value = false
}

function paginateReply(text, maxCharacters = 76) {
  const normalized = text.replace(/\r\n/g, '\n').trim()
  if (!normalized) return ['']

  const pages = []
  let remaining = normalized

  while (remaining.length > maxCharacters) {
    const searchStart = Math.floor(maxCharacters * 0.62)
    const windowText = remaining.slice(searchStart, maxCharacters + 1)
    const strongBreak = findLastBreak(windowText, /[。！？!?；;\n]/)
    const softBreak = findLastBreak(windowText, /[，,、：:]/)
    const offset = strongBreak >= 0 ? strongBreak : softBreak
    const breakAt = offset >= 0 ? searchStart + offset + 1 : maxCharacters
    pages.push(remaining.slice(0, breakAt).trim())
    remaining = remaining.slice(breakAt).trim()
  }

  if (remaining) pages.push(remaining)
  return pages
}

function findLastBreak(text, pattern) {
  for (let index = text.length - 1; index >= 0; index -= 1) {
    if (pattern.test(text[index])) return index
  }
  return -1
}

function getChatErrorMessage(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (status === 503 && detail === 'DEEPSEEK_API_KEY 未配置') {
    return 'DeepSeek API Key 未配置。'
  }
  if (status === 504) return 'DeepSeek 响应超时，请稍后重试。'
  if (status === 502) return detail || 'DeepSeek 服务暂时不可用。'
  return 'AI 服务未响应，请检查本地后端状态。'
}

function sleep(ms) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}
</script>

<style scoped>
.app-root {
  width: 100vw;
  height: 700px;
  position: relative;
  overflow: hidden;
  background: transparent;
  contain: strict;
}
</style>
