const { app, safeStorage } = require('electron')
const { randomBytes } = require('crypto')
const fs = require('fs')
const path = require('path')

const CONFIG_VERSION = 1

function getConfigPath() {
  return path.join(app.getPath('userData'), 'config.json')
}

function readConfig() {
  const configPath = getConfigPath()
  if (!fs.existsSync(configPath)) return { version: CONFIG_VERSION }

  try {
    const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8'))
    return parsed && typeof parsed === 'object'
      ? { version: CONFIG_VERSION, ...parsed }
      : { version: CONFIG_VERSION }
  } catch (error) {
    console.error('[config] 配置读取失败:', error.message)
    return { version: CONFIG_VERSION }
  }
}

function writeConfig(config) {
  const configPath = getConfigPath()
  fs.mkdirSync(path.dirname(configPath), { recursive: true })
  fs.writeFileSync(configPath, JSON.stringify({ ...config, version: CONFIG_VERSION }, null, 2), 'utf8')
}

function getApiKey() {
  const encrypted = readConfig().deepseekApiKey
  if (!encrypted || !safeStorage.isEncryptionAvailable()) return ''

  try {
    return safeStorage.decryptString(Buffer.from(encrypted, 'base64'))
  } catch (error) {
    console.error('[config] DeepSeek Key 解密失败:', error.message)
    return ''
  }
}

function saveApiKey(apiKey) {
  const normalized = String(apiKey || '').trim()
  if (!normalized) throw new Error('DeepSeek API Key 不能为空')
  if (!safeStorage.isEncryptionAvailable()) throw new Error('系统加密服务当前不可用')

  const config = readConfig()
  config.deepseekApiKey = safeStorage.encryptString(normalized).toString('base64')
  writeConfig(config)
}

function getOrCreateLocalApiToken() {
  const config = readConfig()
  if (config.localApiToken && safeStorage.isEncryptionAvailable()) {
    try {
      return safeStorage.decryptString(Buffer.from(config.localApiToken, 'base64'))
    } catch (error) {
      console.error('[config] 本地认证令牌解密失败:', error.message)
    }
  }

  const token = randomBytes(32).toString('hex')
  if (safeStorage.isEncryptionAvailable()) {
    config.localApiToken = safeStorage.encryptString(token).toString('base64')
    writeConfig(config)
  }
  return token
}

function getPublicConfig() {
  const apiKey = getApiKey()
  return {
    apiKeyConfigured: Boolean(apiKey),
    apiKeyHint: apiKey ? `••••${apiKey.slice(-4)}` : '',
    dataDirectory: app.getPath('userData')
  }
}

module.exports = {
  getApiKey,
  getOrCreateLocalApiToken,
  getPublicConfig,
  saveApiKey
}
