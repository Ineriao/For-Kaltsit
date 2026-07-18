const fs = require('fs')
const path = require('path')

const MAX_EVENTS = 500
const MAX_LOG_BYTES = 2 * 1024 * 1024

class DiagnosticsManager {
  constructor(options) {
    this.app = options.app
    this.dialog = options.dialog
    this.startedAt = Date.now()
    this.events = []
    this.statePath = path.join(options.userData, 'diagnostics.json')
    this.logDirectory = path.join(options.userData, 'logs')
    this.logPath = path.join(this.logDirectory, 'runtime.log')
    this.state = this.loadState()
    fs.mkdirSync(this.logDirectory, { recursive: true })
  }

  isSafeMode() {
    return this.state.safeMode
  }

  setSafeMode(enabled) {
    this.state.safeMode = Boolean(enabled)
    this.saveState()
    this.record('runtime', 'info', `安全模式${this.state.safeMode ? '已启用' : '已关闭'}`)
    return this.state.safeMode
  }

  record(service, level, message) {
    const event = {
      at: new Date().toISOString(),
      service: String(service || 'runtime').slice(0, 24),
      level: ['info', 'warn', 'error'].includes(level) ? level : 'info',
      message: redact(String(message || '')).slice(0, 1200)
    }
    this.events.push(event)
    if (this.events.length > MAX_EVENTS) this.events.splice(0, this.events.length - MAX_EVENTS)
    this.appendPersistentLog(event)
    return event
  }

  snapshot(runtime) {
    return {
      app: {
        version: this.app.getVersion(),
        packaged: this.app.isPackaged,
        platform: process.platform,
        arch: process.arch,
        electron: process.versions.electron,
        node: process.versions.node,
        uptime_seconds: Math.floor((Date.now() - this.startedAt) / 1000)
      },
      safeMode: this.state.safeMode,
      runtime,
      events: this.events.slice(-80)
    }
  }

  async exportLogs(parentWindow, snapshot) {
    const result = await this.dialog.showSaveDialog(parentWindow, {
      title: '导出脱敏诊断日志',
      defaultPath: `kaltsit-diagnostics-${new Date().toISOString().slice(0, 10)}.json`,
      filters: [{ name: 'JSON', extensions: ['json'] }]
    })
    if (result.canceled || !result.filePath) return { exported: false }
    fs.writeFileSync(result.filePath, JSON.stringify(snapshot, null, 2), 'utf8')
    return { exported: true, path: result.filePath }
  }

  loadState() {
    try {
      const stored = JSON.parse(fs.readFileSync(this.statePath, 'utf8'))
      return { safeMode: Boolean(stored.safeMode) }
    } catch {
      return { safeMode: false }
    }
  }

  saveState() {
    fs.writeFileSync(this.statePath, JSON.stringify(this.state, null, 2), { encoding: 'utf8', mode: 0o600 })
  }

  appendPersistentLog(event) {
    try {
      const size = fs.existsSync(this.logPath) ? fs.statSync(this.logPath).size : 0
      if (size >= MAX_LOG_BYTES) return
      fs.appendFileSync(this.logPath, `${JSON.stringify(event)}\n`, 'utf8')
    } catch {
      // 诊断日志不能影响主进程运行
    }
  }
}

function redact(message) {
  return message
    .replace(/\bsk-[a-z0-9_-]{8,}\b/gi, '[REDACTED_KEY]')
    .replace(/\bBearer\s+[^\s]+/gi, 'Bearer [REDACTED]')
    .replace(/DEEPSEEK_API_KEY\s*=\s*[^\s]+/gi, 'DEEPSEEK_API_KEY=[REDACTED]')
}

module.exports = { DiagnosticsManager, redact }
