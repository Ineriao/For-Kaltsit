const { autoUpdater } = require('electron-updater')


class UpdateManager {
  constructor(options) {
    this.app = options.app
    this.onState = options.onState
    this.record = options.record
    this.autoCheckTimer = null
    this.state = {
      status: this.app.isPackaged ? 'idle' : 'disabled',
      currentVersion: this.app.getVersion(),
      availableVersion: null,
      progress: 0,
      message: this.app.isPackaged ? '尚未检查更新' : '开发模式不检查更新'
    }

    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = false
    autoUpdater.allowPrerelease = false
    this.bindEvents()
  }

  getState() {
    return { ...this.state }
  }

  startAutomaticCheck() {
    if (!this.app.isPackaged || this.autoCheckTimer) return
    this.autoCheckTimer = setTimeout(() => {
      this.autoCheckTimer = null
      this.check().catch(() => {})
    }, 30000)
    this.autoCheckTimer.unref?.()
  }

  async check() {
    if (!this.app.isPackaged) return this.getState()
    this.updateState({ status: 'checking', progress: 0, message: '正在检查 GitHub Releases' })
    try {
      await autoUpdater.checkForUpdates()
    } catch (error) {
      this.handleError(error)
    }
    return this.getState()
  }

  async download() {
    if (this.state.status !== 'available') throw new Error('当前没有可下载的更新')
    this.updateState({ status: 'downloading', progress: 0, message: '正在下载更新' })
    try {
      await autoUpdater.downloadUpdate()
    } catch (error) {
      this.handleError(error)
    }
    return this.getState()
  }

  install() {
    if (this.state.status !== 'downloaded') throw new Error('更新尚未下载完成')
    this.record?.('updater', 'info', `安装更新 ${this.state.availableVersion || ''}`)
    autoUpdater.quitAndInstall(false, true)
    return true
  }

  dispose() {
    clearTimeout(this.autoCheckTimer)
    this.autoCheckTimer = null
  }

  bindEvents() {
    autoUpdater.on('checking-for-update', () => {
      this.updateState({ status: 'checking', message: '正在检查更新' })
    })
    autoUpdater.on('update-available', info => {
      this.updateState({
        status: 'available',
        availableVersion: info.version,
        message: `发现版本 ${info.version}`
      })
      this.record?.('updater', 'info', `发现更新 ${info.version}`)
    })
    autoUpdater.on('update-not-available', info => {
      this.updateState({
        status: 'up-to-date',
        availableVersion: info?.version || null,
        progress: 0,
        message: '当前已是最新版本'
      })
    })
    autoUpdater.on('download-progress', progress => {
      this.updateState({
        status: 'downloading',
        progress: Math.max(0, Math.min(progress.percent || 0, 100)),
        message: `正在下载 ${Math.round(progress.percent || 0)}%`
      })
    })
    autoUpdater.on('update-downloaded', info => {
      this.updateState({
        status: 'downloaded',
        availableVersion: info.version,
        progress: 100,
        message: '更新已下载，等待安装'
      })
      this.record?.('updater', 'info', `更新 ${info.version} 下载完成`)
    })
    autoUpdater.on('error', error => this.handleError(error))
  }

  handleError(error) {
    const message = sanitizeMessage(error?.message || '更新服务不可用')
    this.updateState({ status: 'error', progress: 0, message })
    this.record?.('updater', 'error', message)
  }

  updateState(changes) {
    this.state = { ...this.state, ...changes }
    this.onState?.(this.getState())
  }
}

function sanitizeMessage(message) {
  return String(message).replace(/https?:\/\/[^\s]+/g, '[update-source]').slice(0, 240)
}

module.exports = { UpdateManager, sanitizeMessage }
