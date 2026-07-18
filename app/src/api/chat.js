import client from './client.js'

const BASE = 'http://127.0.0.1:8765'

/**
 * 发送对话消息，返回凯尔希回复文本
 */
export async function sendMessage(messages, sessionId = null, toolContext = null) {
  const res = await client.post(
    `${BASE}/chat`,
    { messages, session_id: sessionId, tool_context: toolContext },
    { timeout: 120000 }
  )
  return res.data
}

/**
 * 检查本地 AI 服务是否可用
 */
export async function getHealth() {
  const res = await client.get(`${BASE}/health`, { timeout: 1500 })
  return res.data
}

export async function createSession(initialMessage) {
  const res = await client.post(`${BASE}/sessions`, {
    title: '新对话',
    initial_message: initialMessage
  })
  return res.data
}

export async function getSessions() {
  const res = await client.get(`${BASE}/sessions`)
  return res.data.sessions
}

export async function getSessionMessages(sessionId) {
  const res = await client.get(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages`)
  return res.data.messages
}

export async function renameSession(sessionId, title) {
  const res = await client.patch(`${BASE}/sessions/${encodeURIComponent(sessionId)}`, { title })
  return res.data
}

export async function deleteSession(sessionId) {
  await client.delete(`${BASE}/sessions/${encodeURIComponent(sessionId)}`)
}
