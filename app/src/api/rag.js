import client from './client.js'

const BASE = 'http://127.0.0.1:8765'

export async function getRagStatus() {
  const response = await client.get(`${BASE}/rag/status`)
  return response.data
}

export async function downloadRagModel() {
  const response = await client.post(`${BASE}/rag/model/download`, null, { timeout: 600000 })
  return response.data
}

export async function reloadRagModel() {
  const response = await client.post(`${BASE}/rag/model/reload`, null, { timeout: 120000 })
  return response.data
}

export async function getKnowledgeDocuments() {
  const response = await client.get(`${BASE}/knowledge/documents`)
  return response.data.documents
}

export async function importKnowledgeDocument(file) {
  const response = await client.post(`${BASE}/knowledge/documents`, {
    title: file.title,
    source_type: file.sourceType,
    content: file.content
  }, { timeout: 120000 })
  return response.data
}

export async function deleteKnowledgeDocument(documentId) {
  await client.delete(`${BASE}/knowledge/documents/${encodeURIComponent(documentId)}`)
}
