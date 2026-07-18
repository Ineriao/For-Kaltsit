<template>
  <section class="tools-console" aria-label="PRTS 桌面工具">
    <header class="tools-status">
      <span><small>PRTS LOCAL TOOLS / OPT-IN</small><b>桌面工具</b></span>
      <i>{{ enabledCount }} / 4</i>
    </header>

    <div class="permission-grid">
      <label v-for="permission in permissionOptions" :key="permission.key">
        <span><b>{{ permission.label }}</b><small>{{ permission.detail }}</small></span>
        <input
          v-model="state.permissions[permission.key]"
          type="checkbox"
          @change="setPermission(permission.key)"
        >
      </label>
    </div>

    <section class="tool-block">
      <header><span>剪贴板文本</span><small>CLIPBOARD</small></header>
      <p>仅在点击读取时取得当前文本，不后台监听。</p>
      <div class="tool-actions">
        <button type="button" :disabled="busy || !state.permissions.clipboard" @click="readClipboard">读取</button>
        <button type="button" :disabled="!clipboardContext" @click="useContext(clipboardContext)">作为上下文</button>
      </div>
      <pre v-if="clipboardContext">{{ preview(clipboardContext.content) }}</pre>
    </section>

    <section class="tool-block">
      <header><span>单文件阅读</span><small>TEXT FILE</small></header>
      <p>支持 txt、md、json、log、csv、yaml，单个文件不超过 1 MB。</p>
      <div class="tool-actions">
        <button type="button" :disabled="busy || !state.permissions.fileRead" @click="selectFile">选择文件</button>
        <button type="button" :disabled="!fileContext" @click="useContext(fileContext)">作为上下文</button>
      </div>
      <pre v-if="fileContext"><b>{{ fileContext.label }}</b>\n{{ preview(fileContext.content) }}</pre>
    </section>

    <section class="tool-block">
      <header><span>限定目录搜索</span><small>LOCAL SEARCH</small></header>
      <p>{{ state.searchRootName ? `授权目录：${state.searchRootName}` : '尚未选择搜索目录' }}</p>
      <div class="tool-actions">
        <button type="button" :disabled="busy || !state.permissions.directorySearch" @click="chooseRoot">选择目录</button>
      </div>
      <form class="search-form" @submit.prevent="searchFiles">
        <input v-model.trim="searchQuery" type="search" minlength="2" placeholder="文件名或文本关键词">
        <button type="submit" :disabled="busy || !state.permissions.directorySearch || searchQuery.length < 2">检索</button>
      </form>
      <div v-if="searchResult" class="search-result">
        <header>
          <small>SCANNED {{ searchResult.scanned }} / HIT {{ searchResult.results.length }}</small>
          <button type="button" :disabled="!searchResult.results.length" @click="useSearchContext">作为上下文</button>
        </header>
        <p v-if="!searchResult.results.length">没有找到匹配的文本文件。</p>
        <article v-for="result in searchResult.results" :key="result.relativePath">
          <button type="button" title="在资源管理器中显示" @click="showResult(result.relativePath)">
            {{ result.relativePath }}
          </button>
          <small v-if="result.snippet">{{ result.snippet }}</small>
        </article>
      </div>
    </section>

    <section class="tool-block">
      <header><span>屏幕快照</span><small>LOCAL CAPTURE</small></header>
      <p>捕获主屏幕并复制到剪贴板；当前文本模型不会分析图片。</p>
      <div class="tool-actions">
        <button type="button" :disabled="busy || !state.permissions.screenshot" @click="captureScreen">捕获</button>
      </div>
      <img v-if="screenshotUrl" :src="screenshotUrl" alt="刚刚捕获的主屏幕预览">
    </section>

    <p class="tool-message" :class="{ error: messageError }">{{ message }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const emit = defineEmits(['use-context'])

const permissionOptions = [
  { key: 'clipboard', label: '剪贴板', detail: '手动读取当前文本' },
  { key: 'fileRead', label: '文件读取', detail: '仅限用户选中的文件' },
  { key: 'directorySearch', label: '目录搜索', detail: '仅限用户选中的目录' },
  { key: 'screenshot', label: '屏幕快照', detail: '手动捕获主屏幕' }
]

const state = ref({
  permissions: { clipboard: false, fileRead: false, directorySearch: false, screenshot: false },
  searchRoot: '',
  searchRootName: ''
})
const busy = ref(false)
const message = ref('')
const messageError = ref(false)
const clipboardContext = ref(null)
const fileContext = ref(null)
const searchQuery = ref('')
const searchResult = ref(null)
const screenshotUrl = ref('')

const enabledCount = computed(() => Object.values(state.value.permissions).filter(Boolean).length)

onMounted(loadState)

async function loadState() {
  try {
    state.value = await window.electronAPI.getDesktopToolState()
  } catch (error) {
    setMessage(readError(error, '无法读取桌面工具权限'), true)
  }
}

async function setPermission(permission) {
  busy.value = true
  try {
    state.value = await window.electronAPI.setDesktopToolPermission(
      permission,
      state.value.permissions[permission]
    )
    setMessage('权限设置已保存在本机')
  } catch (error) {
    setMessage(readError(error, '权限设置失败'), true)
    await loadState()
  } finally {
    busy.value = false
  }
}

async function readClipboard() {
  await runTool(async () => {
    clipboardContext.value = await window.electronAPI.readClipboardText()
    setMessage(clipboardContext.value.truncated ? '文本较长，已截取前 16000 字' : '剪贴板文本已读取')
  }, '无法读取剪贴板')
}

async function selectFile() {
  await runTool(async () => {
    const result = await window.electronAPI.selectDesktopTextFile()
    if (result.canceled) return
    fileContext.value = result
    setMessage(result.truncated ? '文件较长，已截取前 16000 字' : '文件已读取')
  }, '无法读取文件')
}

async function chooseRoot() {
  await runTool(async () => {
    const result = await window.electronAPI.chooseDesktopSearchRoot()
    if (!result.canceled) {
      state.value = result
      searchResult.value = null
      setMessage(`搜索范围已限定为 ${result.searchRootName}`)
    }
  }, '无法设置搜索目录')
}

async function searchFiles() {
  await runTool(async () => {
    searchResult.value = await window.electronAPI.searchDesktopFiles(searchQuery.value)
    setMessage(searchResult.value.limited ? '已达到 800 个文件的扫描上限' : '本地搜索完成')
  }, '本地搜索失败')
}

async function showResult(relativePath) {
  try {
    await window.electronAPI.showDesktopSearchResult(relativePath)
  } catch (error) {
    setMessage(readError(error, '无法定位文件'), true)
  }
}

async function captureScreen() {
  await runTool(async () => {
    const result = await window.electronAPI.capturePrimaryScreen()
    screenshotUrl.value = result.dataUrl
    setMessage('屏幕快照已复制到剪贴板')
  }, '屏幕捕获失败')
}

function useContext(context) {
  if (!context) return
  emit('use-context', { kind: context.kind, label: context.label, content: context.content })
  setMessage(`已装载上下文：${context.label}`)
}

function useSearchContext() {
  if (!searchResult.value?.results.length) return
  const content = searchResult.value.results
    .map(item => `${item.relativePath}${item.snippet ? `\n${item.snippet}` : ''}`)
    .join('\n\n')
  useContext({ kind: 'search', label: `${searchResult.value.rootName} / ${searchResult.value.query}`, content })
}

async function runTool(operation, fallback) {
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

function preview(content) {
  return content.length > 420 ? `${content.slice(0, 420)}…` : content
}

function readError(error, fallback) {
  const message = String(error?.message || '')
  return message.split('Error: ').at(-1) || fallback
}

function setMessage(text, error = false) {
  message.value = text
  messageError.value = error
}
</script>

<style scoped>
.tools-console { display: grid; gap: 12px; }
.tools-status { display: flex; align-items: end; justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,.24); }
.tools-status span { display: grid; gap: 4px; }
.tools-status small, .tool-block > header small { color: rgba(255,255,255,.4); font: 9px/1 'Novecento Sans', sans-serif; letter-spacing: .13em; }
.tools-status b { font-size: 18px; font-weight: 500; letter-spacing: .08em; }
.tools-status i { color: rgba(255,255,255,.5); font: normal 10px/1 'Novecento Sans', sans-serif; }
.permission-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(255,255,255,.1); }
.permission-grid label { min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px; background: rgba(4,4,4,.92); cursor: pointer; }
.permission-grid span { display: grid; gap: 4px; }
.permission-grid b { font-size: 11px; font-weight: 500; }
.permission-grid small { color: rgba(255,255,255,.35); font-size: 9px; line-height: 1.35; }
.permission-grid input { width: 22px; accent-color: #fff; }
.tool-block { display: grid; gap: 8px; padding: 11px; border-left: 1px solid rgba(255,255,255,.17); background: rgba(255,255,255,.025); }
.tool-block > header, .search-result > header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.tool-block > header span { color: rgba(255,255,255,.72); font-size: 11px; }
.tool-block > p { margin: 0; color: rgba(255,255,255,.38); font-size: 9px; line-height: 1.6; }
.tool-actions { display: flex; justify-content: flex-end; gap: 6px; }
button, input { min-height: 29px; border: 1px solid rgba(255,255,255,.17); color: #fff; background: rgba(0,0,0,.24); font: inherit; }
button { padding: 0 9px; cursor: pointer; transition: border-color .2s, background .2s, transform .15s; }
button:hover:not(:disabled) { border-color: rgba(255,255,255,.6); background: rgba(255,255,255,.07); }
button:active:not(:disabled) { transform: translateY(1px); }
button:disabled { opacity: .27; cursor: default; }
button:focus-visible, input:focus-visible { outline: 1px solid #fff; outline-offset: 2px; }
pre { max-height: 112px; overflow: auto; margin: 0; padding: 9px; color: rgba(255,255,255,.58); background: rgba(0,0,0,.24); font: 9px/1.55 var(--font-mono); white-space: pre-wrap; word-break: break-word; }
.search-form { display: grid; grid-template-columns: 1fr auto; gap: 6px; }
.search-form input { min-width: 0; padding: 0 9px; }
.search-result { display: grid; gap: 5px; max-height: 170px; overflow: auto; padding-top: 7px; border-top: 1px solid rgba(255,255,255,.08); }
.search-result > p { color: rgba(255,255,255,.38); font-size: 10px; }
.search-result article { display: grid; gap: 4px; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,.06); }
.search-result article button { min-height: auto; padding: 0; overflow: hidden; border: 0; color: rgba(255,255,255,.8); background: transparent; font-size: 9px; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.search-result article small { color: rgba(255,255,255,.35); font-size: 8px; line-height: 1.5; }
.tool-block img { width: 100%; max-height: 125px; object-fit: contain; border: 1px solid rgba(255,255,255,.12); filter: grayscale(1); }
.tool-message { min-height: 16px; margin: 0; color: rgba(255,255,255,.55); font-size: 10px; }
.tool-message.error { color: #fff; text-decoration: underline dotted; text-underline-offset: 3px; }
</style>
