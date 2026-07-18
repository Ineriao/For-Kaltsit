import client from './client.js'

const BASE = 'http://127.0.0.1:8765'

export async function getMemories() {
  const response = await client.get(`${BASE}/memories`)
  return response.data
}

export async function createMemory(category, content) {
  const response = await client.post(`${BASE}/memories`, { category, content })
  return response.data
}

export async function updateMemory(memory) {
  const response = await client.patch(`${BASE}/memories/${encodeURIComponent(memory.id)}`, {
    category: memory.category,
    content: memory.content,
    enabled: memory.enabled
  })
  return response.data
}

export async function deleteMemory(memoryId) {
  await client.delete(`${BASE}/memories/${encodeURIComponent(memoryId)}`)
}

export async function updateMemorySettings(settings) {
  const response = await client.patch(`${BASE}/memory/settings`, settings)
  return response.data
}
