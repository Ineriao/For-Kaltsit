const fs = require('fs')
const path = require('path')

const PERMISSION_KEYS = new Set(['clipboard', 'fileRead', 'directorySearch', 'screenshot'])
const TEXT_EXTENSIONS = new Set(['.txt', '.md', '.json', '.log', '.csv', '.tsv', '.yaml', '.yml'])
const MAX_FILE_BYTES = 1024 * 1024
const MAX_CONTEXT_CHARS = 16000
const MAX_SEARCH_FILES = 800
const MAX_SEARCH_RESULTS = 50

class DesktopTools {
  constructor(options) {
    this.dialog = options.dialog
    this.clipboard = options.clipboard
    this.desktopCapturer = options.desktopCapturer
    this.screen = options.screen
    this.shell = options.shell
    this.statePath = path.join(options.userData, 'desktop-tools.json')
    this.state = this.loadState()
  }

  getState() {
    return {
      permissions: { ...this.state.permissions },
      searchRoot: this.state.searchRoot || '',
      searchRootName: this.state.searchRoot ? path.basename(this.state.searchRoot) : ''
    }
  }

  setPermission(permission, enabled) {
    if (!PERMISSION_KEYS.has(permission)) throw new Error('未知桌面权限')
    this.state.permissions[permission] = Boolean(enabled)
    this.saveState()
    return this.getState()
  }

  readClipboard() {
    this.requirePermission('clipboard')
    const content = this.clipboard.readText().trim()
    if (!content) throw new Error('剪贴板中没有文本')
    return {
      kind: 'clipboard',
      label: '剪贴板文本',
      content: content.slice(0, MAX_CONTEXT_CHARS),
      truncated: content.length > MAX_CONTEXT_CHARS
    }
  }

  async selectTextFile(parentWindow) {
    this.requirePermission('fileRead')
    const result = await this.dialog.showOpenDialog(parentWindow, {
      title: '选择交给 PRTS 阅读的文本文件',
      properties: ['openFile'],
      filters: [
        { name: '文本资料', extensions: [...TEXT_EXTENSIONS].map(extension => extension.slice(1)) }
      ]
    })
    if (result.canceled || !result.filePaths[0]) return { canceled: true }
    return this.readSelectedFile(result.filePaths[0])
  }

  async chooseSearchRoot(parentWindow) {
    this.requirePermission('directorySearch')
    const result = await this.dialog.showOpenDialog(parentWindow, {
      title: '选择允许 PRTS 搜索的目录',
      properties: ['openDirectory']
    })
    if (result.canceled || !result.filePaths[0]) return { canceled: true, ...this.getState() }
    this.state.searchRoot = path.resolve(result.filePaths[0])
    this.saveState()
    return { canceled: false, ...this.getState() }
  }

  async searchFiles(query) {
    this.requirePermission('directorySearch')
    const normalizedQuery = String(query || '').trim().toLocaleLowerCase()
    if (normalizedQuery.length < 2) throw new Error('搜索词至少需要 2 个字符')
    const root = this.state.searchRoot
    if (!root || !fs.existsSync(root)) throw new Error('请先选择允许搜索的目录')

    const results = []
    let scanned = 0
    const pending = [root]
    while (pending.length && scanned < MAX_SEARCH_FILES && results.length < MAX_SEARCH_RESULTS) {
      const directory = pending.shift()
      let entries
      try {
        entries = await fs.promises.readdir(directory, { withFileTypes: true })
      } catch {
        continue
      }

      for (const entry of entries) {
        if (scanned >= MAX_SEARCH_FILES) break
        if (entry.name.startsWith('.') || results.length >= MAX_SEARCH_RESULTS) continue
        const absolutePath = path.join(directory, entry.name)
        if (entry.isDirectory()) {
          pending.push(absolutePath)
          continue
        }
        if (!entry.isFile() || !TEXT_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) continue
        scanned += 1
        const relativePath = path.relative(root, absolutePath)
        const filenameMatch = relativePath.toLocaleLowerCase().includes(normalizedQuery)
        let content = ''
        try {
          const stats = await fs.promises.stat(absolutePath)
          if (stats.size <= 256 * 1024) content = await fs.promises.readFile(absolutePath, 'utf8')
        } catch {
          continue
        }
        const contentIndex = content.toLocaleLowerCase().indexOf(normalizedQuery)
        if (!filenameMatch && contentIndex < 0) continue
        const snippetStart = Math.max(0, contentIndex - 70)
        const snippet = contentIndex >= 0
          ? content.slice(snippetStart, snippetStart + 220).replace(/\s+/g, ' ').trim()
          : ''
        results.push({ relativePath, snippet })
      }
    }

    return {
      query: String(query).trim(),
      rootName: path.basename(root),
      scanned,
      limited: scanned >= MAX_SEARCH_FILES,
      results
    }
  }

  showSearchResult(relativePath) {
    this.requirePermission('directorySearch')
    const root = this.state.searchRoot
    if (!root) throw new Error('搜索目录尚未设置')
    const target = path.resolve(root, relativePath)
    if (!isWithin(root, target) || !fs.existsSync(target)) throw new Error('搜索结果路径无效')
    this.shell.showItemInFolder(target)
    return true
  }

  async capturePrimaryScreen() {
    this.requirePermission('screenshot')
    const display = this.screen.getPrimaryDisplay()
    const scale = Math.min(1, 1920 / display.size.width)
    const thumbnailSize = {
      width: Math.max(1, Math.round(display.size.width * scale)),
      height: Math.max(1, Math.round(display.size.height * scale))
    }
    const sources = await this.desktopCapturer.getSources({ types: ['screen'], thumbnailSize })
    const source = sources.find(item => String(item.display_id) === String(display.id)) || sources[0]
    if (!source || source.thumbnail.isEmpty()) throw new Error('无法捕获主屏幕')
    this.clipboard.writeImage(source.thumbnail)
    return {
      dataUrl: source.thumbnail.toDataURL(),
      width: thumbnailSize.width,
      height: thumbnailSize.height,
      copied: true
    }
  }

  readSelectedFile(filePath) {
    const extension = path.extname(filePath).toLowerCase()
    if (!TEXT_EXTENSIONS.has(extension)) throw new Error('仅允许读取文本类文件')
    const stats = fs.statSync(filePath)
    if (!stats.isFile() || stats.size > MAX_FILE_BYTES) throw new Error('文件无效或超过 1 MB 限制')
    const content = fs.readFileSync(filePath, 'utf8').trim()
    if (!content) throw new Error('文件没有可读取的文本')
    return {
      canceled: false,
      kind: 'file',
      label: path.basename(filePath),
      content: content.slice(0, MAX_CONTEXT_CHARS),
      truncated: content.length > MAX_CONTEXT_CHARS
    }
  }

  requirePermission(permission) {
    if (!this.state.permissions[permission]) throw new Error('请先启用对应的本地权限')
  }

  loadState() {
    const defaults = {
      permissions: { clipboard: false, fileRead: false, directorySearch: false, screenshot: false },
      searchRoot: ''
    }
    try {
      const stored = JSON.parse(fs.readFileSync(this.statePath, 'utf8'))
      return {
        permissions: Object.fromEntries(
          [...PERMISSION_KEYS].map(key => [key, Boolean(stored.permissions?.[key])])
        ),
        searchRoot: typeof stored.searchRoot === 'string' ? stored.searchRoot : ''
      }
    } catch {
      return defaults
    }
  }

  saveState() {
    fs.writeFileSync(this.statePath, JSON.stringify(this.state, null, 2), { encoding: 'utf8', mode: 0o600 })
  }
}

function isWithin(root, target) {
  const relative = path.relative(path.resolve(root), path.resolve(target))
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative))
}

module.exports = { DesktopTools, isWithin }
