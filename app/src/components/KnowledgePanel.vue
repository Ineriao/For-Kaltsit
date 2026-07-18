<template>
  <div class="knowledge-panel">
    <section class="terminal-section">
      <header>
        <span>检索引擎</span>
        <small>{{ ragStatus.ready ? 'HYBRID / FTS5 + VECTOR' : 'FTS5 KEYWORD' }}</small>
      </header>
      <div class="engine-state">
        <span>
          <b>BAAI / BGE SMALL ZH</b>
          <small>{{ ragStatus.ready ? `READY · ${ragStatus.source?.toUpperCase()}` : 'VECTOR MODEL OFFLINE' }}</small>
        </span>
        <i :class="{ ready: ragStatus.ready }" />
      </div>
      <div class="action-grid">
        <button type="button" :disabled="busy" @click="importFiles">导入资料</button>
        <button v-if="!ragStatus.ready" type="button" :disabled="busy" @click="downloadModel">下载模型</button>
        <button v-if="!ragStatus.ready" type="button" :disabled="busy" @click="importModel">手动导入</button>
      </div>
      <p class="format-note">TXT / MD / JSON / HTML / PDF / DOCX / IMAGE OCR</p>
    </section>

    <section class="terminal-section">
      <header>
        <span>知识分组</span>
        <small>{{ collections.length.toString().padStart(2, '0') }} GROUPS</small>
      </header>
      <form class="collection-create" @submit.prevent="createCollection">
        <input v-model.trim="newCollectionName" maxlength="60" placeholder="新分组名称">
        <button type="submit" :disabled="busy || !newCollectionName">新增</button>
      </form>
      <div class="collection-list">
        <button
          v-for="collection in collections"
          :key="collection.id"
          type="button"
          :class="{ active: selectedCollectionId === collection.id, disabled: !collection.enabled }"
          @click="selectedCollectionId = collection.id"
        >
          <span>{{ collection.name }}</span>
          <small>{{ collection.document_count }}</small>
          <i
            role="switch"
            :aria-checked="collection.enabled"
            :title="collection.enabled ? '停用分组' : '启用分组'"
            @click.stop="toggleCollection(collection)"
          />
        </button>
      </div>
    </section>

    <section class="terminal-section">
      <header>
        <span>资料索引</span>
        <small>{{ filteredDocuments.length.toString().padStart(2, '0') }} FILES</small>
      </header>
      <div class="document-list">
        <p v-if="!filteredDocuments.length" class="empty-state">当前分组尚无资料</p>
        <article v-for="document in filteredDocuments" :key="document.id" :class="{ disabled: !document.enabled }">
          <button
            type="button"
            class="document-toggle"
            :aria-label="document.enabled ? '停用资料' : '启用资料'"
            :title="document.enabled ? '停用资料' : '启用资料'"
            @click="toggleDocument(document)"
          ><i /></button>
          <span>
            <b>{{ document.title }}</b>
            <small>
              {{ document.source_type.toUpperCase() }} · {{ document.indexed_count }}/{{ document.chunk_count }} CHUNKS
              <template v-if="document.metadata?.ocr"> · OCR</template>
            </small>
          </span>
          <button type="button" class="remove-button" :disabled="busy" @click="requestDelete(document.id)">
            {{ deleteArmedId === document.id ? '确认' : '移除' }}
          </button>
        </article>
      </div>
      <p v-if="message" class="panel-message">{{ message }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  createKnowledgeCollection,
  deleteKnowledgeDocument,
  downloadRagModel,
  getKnowledgeCollections,
  getKnowledgeDocuments,
  getRagStatus,
  importKnowledgeDocument,
  reloadRagModel,
  setKnowledgeDocumentEnabled,
  updateKnowledgeCollection
} from '../api/rag.js'

const props = defineProps({ backendReady: Boolean })

const ragStatus = ref({ ready: false, source: null })
const collections = ref([])
const documents = ref([])
const selectedCollectionId = ref('default')
const newCollectionName = ref('')
const busy = ref(false)
const message = ref('')
const deleteArmedId = ref(null)

const filteredDocuments = computed(() => (
  documents.value.filter(document => document.collection_id === selectedCollectionId.value)
))

watch(() => props.backendReady, ready => {
  if (ready) loadState()
})

onMounted(() => {
  if (props.backendReady) loadState()
})

async function loadState() {
  try {
    const [status, nextCollections, nextDocuments] = await Promise.all([
      getRagStatus(),
      getKnowledgeCollections(),
      getKnowledgeDocuments()
    ])
    ragStatus.value = status
    collections.value = nextCollections
    documents.value = nextDocuments
    if (!nextCollections.some(collection => collection.id === selectedCollectionId.value)) {
      selectedCollectionId.value = nextCollections[0]?.id || 'default'
    }
  } catch (error) {
    message.value = getRequestError(error, '知识库状态读取失败')
  }
}

async function importFiles() {
  busy.value = true
  message.value = ''
  try {
    const result = await window.electronAPI.selectKnowledgeFiles()
    if (result?.canceled) return
    if (result?.error) throw new Error(result.error)
    const counts = { created: 0, updated: 0, unchanged: 0 }
    for (const file of result.files || []) {
      const document = await importKnowledgeDocument({
        ...file,
        collectionId: selectedCollectionId.value
      })
      counts[document.import_status] = (counts[document.import_status] || 0) + 1
    }
    await loadState()
    message.value = `新增 ${counts.created} · 更新 ${counts.updated} · 未变化 ${counts.unchanged}`
  } catch (error) {
    message.value = getRequestError(error, '资料导入失败')
  } finally {
    busy.value = false
  }
}

async function createCollection() {
  if (!newCollectionName.value) return
  busy.value = true
  message.value = ''
  try {
    const collection = await createKnowledgeCollection(newCollectionName.value)
    newCollectionName.value = ''
    await loadState()
    selectedCollectionId.value = collection.id
  } catch (error) {
    message.value = getRequestError(error, '知识分组创建失败')
  } finally {
    busy.value = false
  }
}

async function toggleCollection(collection) {
  busy.value = true
  try {
    await updateKnowledgeCollection({ ...collection, enabled: !collection.enabled })
    await loadState()
  } catch (error) {
    message.value = getRequestError(error, '知识分组更新失败')
  } finally {
    busy.value = false
  }
}

async function toggleDocument(document) {
  busy.value = true
  try {
    await setKnowledgeDocumentEnabled(document.id, !document.enabled)
    await loadState()
  } catch (error) {
    message.value = getRequestError(error, '资料状态更新失败')
  } finally {
    busy.value = false
  }
}

async function downloadModel() {
  busy.value = true
  message.value = '正在下载并初始化语义模型。'
  try {
    if (window.electronAPI?.downloadEmbeddingModel) {
      await window.electronAPI.downloadEmbeddingModel()
      ragStatus.value = await reloadRagModel()
    } else {
      ragStatus.value = await downloadRagModel()
    }
    await loadState()
    message.value = '语义模型已就绪，索引已补齐。'
  } catch (error) {
    message.value = getRequestError(error, '模型下载失败')
  } finally {
    busy.value = false
  }
}

async function importModel() {
  busy.value = true
  message.value = ''
  try {
    const result = await window.electronAPI.importEmbeddingModel()
    if (result?.canceled) return
    if (!result?.imported) throw new Error(result?.error || '模型导入失败')
    ragStatus.value = await reloadRagModel()
    await loadState()
    message.value = '本地语义模型已加载。'
  } catch (error) {
    message.value = getRequestError(error, '模型导入失败')
  } finally {
    busy.value = false
  }
}

async function requestDelete(documentId) {
  if (deleteArmedId.value !== documentId) {
    deleteArmedId.value = documentId
    return
  }
  deleteArmedId.value = null
  busy.value = true
  try {
    await deleteKnowledgeDocument(documentId)
    await loadState()
  } catch (error) {
    message.value = getRequestError(error, '资料移除失败')
  } finally {
    busy.value = false
  }
}

function getRequestError(error, fallback) {
  return error.response?.data?.detail || error.message || fallback
}
</script>

<style scoped>
.knowledge-panel { display: grid; gap: 11px; }
.terminal-section { padding-top: 9px; border-top: 1px solid rgba(255, 255, 255, 0.1); }
.terminal-section:first-child { padding-top: 0; border-top: 0; }
.terminal-section > header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
.terminal-section > header span { color: rgba(255, 255, 255, 0.76); font-size: 8px; }
.terminal-section > header small { color: rgba(255, 255, 255, 0.28); font: 5.8px var(--font-mono); }
.engine-state { display: flex; align-items: center; justify-content: space-between; padding: 8px; border-left: 1px solid rgba(255, 255, 255, 0.14); background: rgba(0, 0, 0, 0.18); }
.engine-state b, .engine-state small { display: block; }
.engine-state b { color: rgba(255, 255, 255, 0.72); font: 7px 'Novecento Sans', sans-serif; letter-spacing: 0.08em; }
.engine-state small { margin-top: 4px; color: rgba(255, 255, 255, 0.26); font: 5.8px var(--font-mono); }
.engine-state i { width: 5px; height: 5px; border: 1px solid rgba(255, 255, 255, 0.22); transform: rotate(45deg); }
.engine-state i.ready { border-color: white; background: white; box-shadow: 0 0 9px rgba(255, 255, 255, 0.7); }
.action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: 5px; }
button, input { border: 1px solid rgba(255, 255, 255, 0.11); color: rgba(255, 255, 255, 0.52); background: rgba(255, 255, 255, 0.018); font-size: 6.5px; }
button { min-height: 26px; transition: color 150ms ease, border-color 150ms ease, background 150ms ease; }
button:hover:not(:disabled) { border-color: rgba(255, 255, 255, 0.3); color: white; background: rgba(255, 255, 255, 0.05); }
button:disabled { opacity: 0.28; }
.format-note { margin: 6px 0 0; color: rgba(255, 255, 255, 0.2); font: 5.5px var(--font-mono); letter-spacing: 0.04em; }
.collection-create { display: grid; grid-template-columns: 1fr 48px; gap: 4px; }
.collection-create input { min-width: 0; height: 28px; padding: 0 7px; outline: none; }
.collection-create input:focus { border-color: rgba(255, 255, 255, 0.38); }
.collection-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px; margin-top: 5px; }
.collection-list > button { min-width: 0; display: grid; grid-template-columns: 1fr auto 12px; align-items: center; gap: 4px; padding: 0 6px; text-align: left; }
.collection-list > button.active { color: white; border-color: rgba(255, 255, 255, 0.36); box-shadow: inset 0 -1px 0 white; }
.collection-list > button.disabled { opacity: 0.38; }
.collection-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.collection-list small { font: 5.5px var(--font-mono); }
.collection-list i { width: 8px; height: 4px; border: 1px solid currentColor; }
.collection-list > button:not(.disabled) i { background: currentColor; box-shadow: 0 0 5px rgba(255, 255, 255, 0.5); }
.document-list { max-height: 238px; overflow-y: auto; }
.document-list article { display: grid; grid-template-columns: 23px minmax(0, 1fr) 39px; align-items: stretch; min-height: 42px; margin-bottom: 3px; background: rgba(0, 0, 0, 0.16); }
.document-list article.disabled { opacity: 0.38; }
.document-toggle, .remove-button { min-height: 100%; border-width: 0 1px 0 0; }
.remove-button { border-width: 0 0 0 1px; }
.document-toggle i { display: inline-block; width: 5px; height: 5px; border: 1px solid rgba(255, 255, 255, 0.4); transform: rotate(45deg); }
.document-list article:not(.disabled) .document-toggle i { background: white; box-shadow: 0 0 6px rgba(255, 255, 255, 0.65); }
.document-list article > span { min-width: 0; align-self: center; padding: 0 7px; }
.document-list b, .document-list small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.document-list b { color: rgba(255, 255, 255, 0.72); font-size: 7.5px; font-weight: 520; }
.document-list small { margin-top: 4px; color: rgba(255, 255, 255, 0.25); font: 5.6px var(--font-mono); }
.empty-state { margin: 24px 0; color: rgba(255, 255, 255, 0.2); font-size: 7px; text-align: center; }
.panel-message { margin: 7px 0 0; color: rgba(255, 255, 255, 0.48); font-size: 6.5px; line-height: 1.5; }
</style>
