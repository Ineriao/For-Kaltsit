import axios from 'axios'

const BASE = 'http://127.0.0.1:8765'

/**
 * 发送对话消息，返回凯尔希回复文本
 */
export async function sendMessage(messages) {
  const res = await axios.post(`${BASE}/chat`, { messages }, { timeout: 60000 })
  return res.data.reply
}
