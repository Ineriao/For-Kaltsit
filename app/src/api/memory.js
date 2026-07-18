import axios from 'axios'

const BASE = 'http://127.0.0.1:8765'

export async function getMemories() {
  const response = await axios.get(`${BASE}/memories`)
  return response.data
}

export async function createMemory(category, content) {
  const response = await axios.post(`${BASE}/memories`, { category, content })
  return response.data
}

export async function updateMemory(memory) {
  const response = await axios.patch(`${BASE}/memories/${encodeURIComponent(memory.id)}`, {
    category: memory.category,
    content: memory.content,
    enabled: memory.enabled
  })
  return response.data
}

export async function deleteMemory(memoryId) {
  await axios.delete(`${BASE}/memories/${encodeURIComponent(memoryId)}`)
}

export async function updateMemorySettings(settings) {
  const response = await axios.patch(`${BASE}/memory/settings`, settings)
  return response.data
}
