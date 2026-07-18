<template>
  <section class="memory-console" aria-label="长期记忆">
    <header class="memory-status">
      <span>
        <small>LOCAL MEMORY / {{ memories.length.toString().padStart(2, '0') }}</small>
        <b>长期记忆</b>
      </span>
      <i :class="{ active: settings.enabled }" />
    </header>

    <div class="memory-switches">
      <label>
        <span><b>允许使用记忆</b><small>关闭后不注入任何长期信息</small></span>
        <input v-model="settings.enabled" type="checkbox" @change="saveSettings">
      </label>
      <label>
        <span><b>自动捕获</b><small>仅提取明确表达的稳定事实</small></span>
        <input v-model="settings.auto_capture" type="checkbox" :disabled="!settings.enabled" @change="saveSettings">
      </label>
    </div>

    <form class="memory-create" @submit.prevent="addMemory">
      <select v-model="draftCategory" aria-label="记忆类别">
        <option v-for="option in categoryOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <textarea
        v-model.trim="draftContent"
        maxlength="180"
        rows="2"
        placeholder="手动写入一条需要跨会话保留的事实"
      />
      <button type="submit" :disabled="busy || !draftContent">写入</button>
    </form>

    <div class="memory-list">
      <p v-if="loading" class="memory-empty">正在读取本地记忆…</p>
      <p v-else-if="!memories.length" class="memory-empty">尚无长期记忆。只有明确事实才值得保留。</p>
      <article v-for="memory in memories" :key="memory.id" :class="{ disabled: !memory.enabled }">
        <template v-if="editingId === memory.id">
          <div class="memory-edit">
            <select v-model="editingCategory">
              <option v-for="option in categoryOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <textarea v-model.trim="editingContent" maxlength="180" rows="3" />
            <span>
              <button type="button" @click="cancelEdit">取消</button>
              <button type="button" :disabled="busy || !editingContent" @click="commitEdit(memory)">保存</button>
            </span>
          </div>
        </template>
        <template v-else>
          <header>
            <span>{{ categoryLabel(memory.category) }}</span>
            <small>{{ memory.origin === 'automatic' ? 'AUTO' : 'MANUAL' }}</small>
          </header>
          <p>{{ memory.content }}</p>
          <small v-if="memory.source_excerpt" class="memory-source">来源：{{ memory.source_excerpt }}</small>
          <footer>
            <button type="button" :disabled="busy" @click="toggleMemory(memory)">
              {{ memory.enabled ? '停用' : '启用' }}
            </button>
            <button type="button" :disabled="busy" @click="beginEdit(memory)">修订</button>
            <button type="button" :disabled="busy" @click="forgetMemory(memory.id)">
              {{ deleteArmedId === memory.id ? '确认遗忘' : '遗忘' }}
            </button>
          </footer>
        </template>
      </article>
    </div>

    <p class="memory-message" :class="{ error: messageError }">{{ message }}</p>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import {
  createMemory,
  deleteMemory,
  getMemories,
  updateMemory,
  updateMemorySettings
} from '../api/memory.js'

const props = defineProps({
  backendReady: Boolean,
  refreshToken: { type: Number, default: 0 }
})

const categoryOptions = [
  { value: 'identity', label: '身份' },
  { value: 'preference', label: '偏好' },
  { value: 'commitment', label: '约定' },
  { value: 'event', label: '事件' }
]

const memories = ref([])
const settings = ref({ enabled: true, auto_capture: true })
const loading = ref(false)
const busy = ref(false)
const message = ref('')
const messageError = ref(false)
const draftCategory = ref('preference')
const draftContent = ref('')
const editingId = ref(null)
const editingCategory = ref('preference')
const editingContent = ref('')
const deleteArmedId = ref(null)

watch(() => props.backendReady, ready => {
  if (ready) loadState()
})

watch(() => props.refreshToken, () => {
  if (props.backendReady) loadState(false)
})

onMounted(() => {
  if (props.backendReady) loadState()
})

async function loadState(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const state = await getMemories()
    memories.value = state.memories || []
    settings.value = state.settings || settings.value
    setMessage('')
  } catch (error) {
    setMessage(error.response?.data?.detail || '无法读取长期记忆', true)
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  busy.value = true
  try {
    settings.value = await updateMemorySettings(settings.value)
    setMessage('记忆策略已更新')
  } catch (error) {
    setMessage(error.response?.data?.detail || '记忆策略保存失败', true)
    await loadState(false)
  } finally {
    busy.value = false
  }
}

async function addMemory() {
  if (!draftContent.value || busy.value) return
  busy.value = true
  try {
    await createMemory(draftCategory.value, draftContent.value)
    draftContent.value = ''
    setMessage('记忆已写入本地')
    await loadState(false)
  } catch (error) {
    setMessage(error.response?.data?.detail || '记忆写入失败', true)
  } finally {
    busy.value = false
  }
}

function beginEdit(memory) {
  deleteArmedId.value = null
  editingId.value = memory.id
  editingCategory.value = memory.category
  editingContent.value = memory.content
}

function cancelEdit() {
  editingId.value = null
  editingContent.value = ''
}

async function commitEdit(memory) {
  if (!editingContent.value || busy.value) return
  busy.value = true
  try {
    await updateMemory({
      ...memory,
      category: editingCategory.value,
      content: editingContent.value
    })
    cancelEdit()
    setMessage('记忆已修订')
    await loadState(false)
  } catch (error) {
    setMessage(error.response?.data?.detail || '记忆修订失败', true)
  } finally {
    busy.value = false
  }
}

async function toggleMemory(memory) {
  busy.value = true
  try {
    await updateMemory({ ...memory, enabled: !memory.enabled })
    setMessage(memory.enabled ? '该记忆已停用' : '该记忆已启用')
    await loadState(false)
  } catch (error) {
    setMessage(error.response?.data?.detail || '记忆状态更新失败', true)
  } finally {
    busy.value = false
  }
}

async function forgetMemory(memoryId) {
  if (deleteArmedId.value !== memoryId) {
    deleteArmedId.value = memoryId
    return
  }
  busy.value = true
  try {
    await deleteMemory(memoryId)
    deleteArmedId.value = null
    setMessage('记忆已遗忘')
    await loadState(false)
  } catch (error) {
    setMessage(error.response?.data?.detail || '无法遗忘该记忆', true)
  } finally {
    busy.value = false
  }
}

function categoryLabel(category) {
  return categoryOptions.find(option => option.value === category)?.label || category
}

function setMessage(text, error = false) {
  message.value = text
  messageError.value = error
}
</script>

<style scoped>
.memory-console { display: grid; gap: 14px; }
.memory-status { display: flex; align-items: end; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,.24); }
.memory-status span { display: grid; gap: 4px; }
.memory-status small { color: rgba(255,255,255,.42); font: 10px/1 'Novecento Sans', sans-serif; letter-spacing: .13em; }
.memory-status b { font-size: 18px; font-weight: 500; letter-spacing: .08em; }
.memory-status i { width: 9px; height: 9px; border: 1px solid rgba(255,255,255,.45); transform: rotate(45deg); transition: background .22s, box-shadow .22s; }
.memory-status i.active { background: #fff; box-shadow: 0 0 12px rgba(255,255,255,.7); }
.memory-switches { display: grid; border-block: 1px solid rgba(255,255,255,.1); }
.memory-switches label { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 52px; border-bottom: 1px solid rgba(255,255,255,.08); cursor: pointer; }
.memory-switches label:last-child { border-bottom: 0; }
.memory-switches span { display: grid; gap: 4px; }
.memory-switches b { font-size: 12px; font-weight: 500; }
.memory-switches small { color: rgba(255,255,255,.42); font-size: 10px; }
.memory-switches input { width: 30px; accent-color: #fff; }
.memory-create { display: grid; grid-template-columns: 84px 1fr; gap: 8px; }
.memory-create textarea { grid-column: 1 / -1; }
.memory-create button { grid-column: 2; justify-self: end; min-width: 78px; }
select, textarea, button { border: 1px solid rgba(255,255,255,.2); background: rgba(0,0,0,.22); color: #fff; font: inherit; }
select, button { min-height: 30px; padding: 0 10px; }
textarea { width: 100%; padding: 9px 10px; resize: vertical; line-height: 1.5; }
button { cursor: pointer; transition: color .2s, border-color .2s, background .2s, transform .15s; }
button:hover:not(:disabled) { border-color: rgba(255,255,255,.65); background: rgba(255,255,255,.08); }
button:active:not(:disabled) { transform: translateY(1px); }
button:focus-visible, select:focus-visible, textarea:focus-visible { outline: 1px solid #fff; outline-offset: 2px; }
button:disabled, input:disabled { opacity: .3; cursor: default; }
.memory-list { display: grid; gap: 1px; background: rgba(255,255,255,.1); }
.memory-list article { display: grid; gap: 8px; padding: 12px; background: rgba(5,5,5,.92); transition: opacity .2s; }
.memory-list article.disabled { opacity: .45; }
.memory-list article > header, .memory-list article > footer { display: flex; align-items: center; gap: 6px; }
.memory-list article > header span { font: 10px/1 'Novecento Sans', sans-serif; letter-spacing: .16em; }
.memory-list article > header small { margin-left: auto; color: rgba(255,255,255,.35); font-size: 9px; }
.memory-list article p { margin: 0; color: rgba(255,255,255,.86); font-size: 12px; line-height: 1.6; text-wrap: pretty; }
.memory-source { overflow: hidden; color: rgba(255,255,255,.32); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.memory-list article > footer { justify-content: flex-end; }
.memory-list article > footer button { min-height: 25px; padding-inline: 8px; border-color: rgba(255,255,255,.12); font-size: 10px; }
.memory-edit { display: grid; gap: 8px; }
.memory-edit span { display: flex; justify-content: flex-end; gap: 6px; }
.memory-empty { margin: 0; padding: 26px 18px; background: rgba(5,5,5,.92); color: rgba(255,255,255,.38); font-size: 11px; line-height: 1.7; }
.memory-message { min-height: 16px; margin: 0; color: rgba(255,255,255,.55); font-size: 10px; }
.memory-message.error { color: #fff; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px; }
</style>
