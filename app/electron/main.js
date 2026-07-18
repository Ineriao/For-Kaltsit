const { app, BrowserWindow, ipcMain, Menu, nativeImage, screen, Tray } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const net = require('net')
const path = require('path')
const {
  getImportedAssetsDirectory,
  selectAndImportAssets,
  validateAssetsDirectory
} = require('./asset-manager')
const { getApiKey, getPublicConfig, saveApiKey } = require('./config-store')
const {
  downloadEmbeddingModel,
  selectAndImportEmbeddingModel,
  selectKnowledgeFiles
} = require('./knowledge-manager')

const COLLAPSED_SIZE = { width: 500, height: 700 }
const EXPANDED_SIZE = { width: 860, height: 700 }
const HOST = '127.0.0.1'
const BACKEND_PORT = 8765
const PET_PORT = 8766
const ELECTRON_PORT = 8767
const SPRITE_FILENAME = '立绘_凯尔希·思衡托_1.png'
const RESTART_LIMIT = 3
const RESTART_STABLE_MS = 30000
const RUNTIME_MONITOR_MS = 5000
const ALLOWED_PET_ACTIONS = new Set([
  'RELAX',
  'SIT',
  'SLEEP',
  'MOVE_LEFT',
  'MOVE_RIGHT',
  'SPECIAL',
  'TOUCH'
])
const isDev = !app.isPackaged
const projectRoot = path.resolve(__dirname, '../..')

let mainWindow = null
let tray = null
let petSocketServer = null
let backendProcess = null
let petProcess = null
let backendRestartTimer = null
let petRestartTimer = null
let backendRestartAttempts = 0
let petRestartAttempts = 0
let backendStarting = false
let petStarting = false
let backendRestartRequested = false
let petRestartRequested = false
let shuttingDown = false
let setupRequired = true
let setupMode = false
let settingsExpanded = false
let collapsedBounds = null
let applyingWindowBounds = false
let mouseHitTestTimer = null
let runtimeMonitorTimer = null
let runtimeMonitorRunning = false
let backendStabilityTimer = null
let petStabilityTimer = null
let backendMonitorFailures = 0
let petMonitorFailures = 0
let mouseEventsIgnored = false
let spriteAlphaMask = null
let hitRegions = {
  sprite: { x: -800, y: -620, width: 1920, height: 1920 },
  historyOpen: false,
  settingsOpen: false
}

const runtimeStatus = {
  backend: 'checking',
  pet: 'checking',
  aiConfigured: null
}

const hasSingleInstanceLock = app.requestSingleInstanceLock()

if (!hasSingleInstanceLock) {
  app.quit()
} else {
  registerIpcHandlers()

  app.on('second-instance', openChat)
  app.on('before-quit', () => { shuttingDown = true })
  app.on('will-quit', cleanupRuntime)
  app.on('window-all-closed', () => {})

  app.whenReady().then(bootstrap).catch(error => {
    console.error('[runtime] 启动失败:', error)
    requestQuit()
  })
}

async function bootstrap() {
  await startPetSocketServer()
  createWindow()
  createTray()
  startMouseHitTesting()

  const setupState = getSetupState()
  setupRequired = !setupState.complete
  if (setupRequired) {
    openSetup()
    return
  }

  loadSpriteAlphaMask()
  await startRuntimeServices()
}

async function startRuntimeServices() {
  await Promise.allSettled([
    startBackend(),
    startPet()
  ])
  startRuntimeMonitoring()
}

function createWindow() {
  mainWindow = new BrowserWindow({
    ...COLLAPSED_SIZE,
    useContentSize: true,
    minWidth: COLLAPSED_SIZE.width,
    maxWidth: EXPANDED_SIZE.width,
    minHeight: COLLAPSED_SIZE.height,
    maxHeight: COLLAPSED_SIZE.height,
    frame: false,
    transparent: true,
    resizable: false,
    show: false,
    center: true,
    alwaysOnTop: false,
    skipTaskbar: false,
    hasShadow: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.webContents.on('did-finish-load', () => {
    broadcastRuntimeStatus()
    if (setupMode) mainWindow.webContents.send('setup-show', getSetupState())
  })

  mainWindow.on('close', event => {
    if (shuttingDown) return
    event.preventDefault()
    if (setupMode) {
      mainWindow.hide()
      return
    }
    setImmediate(showPet)
  })

  mainWindow.on('closed', () => { mainWindow = null })
  mainWindow.on('resize', enforceWindowSize)
  mainWindow.on('move', rememberCollapsedBounds)
}

function enforceWindowSize() {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const targetSize = settingsExpanded ? EXPANDED_SIZE : COLLAPSED_SIZE
  const [width, height] = mainWindow.getContentSize()
  if (!applyingWindowBounds && (width !== targetSize.width || height !== targetSize.height)) {
    mainWindow.setContentSize(targetSize.width, targetSize.height)
  }
}

function rememberCollapsedBounds() {
  if (!mainWindow || settingsExpanded || applyingWindowBounds) return
  collapsedBounds = mainWindow.getBounds()
}

function createTray() {
  const iconPath = path.join(__dirname, '../public/tray.png')
  const icon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : createFallbackTrayIcon()

  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('凯尔希 · PRTS')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '展开对话', click: openChat },
    { label: '显示桌宠', click: showPet },
    { type: 'separator' },
    { label: '退出', click: requestQuit }
  ]))

  tray.on('click', () => {
    if (setupMode && mainWindow?.isVisible()) mainWindow.hide()
    else if (mainWindow?.isVisible()) showPet()
    else openChat()
  })
}

function createFallbackTrayIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="6" fill="#050505"/>
      <path d="M16 5 27 16 16 27 5 16Z" fill="none" stroke="#ffffff" stroke-width="2"/>
      <path d="M16 10v12M10 16h12" stroke="#ffffff" stroke-width="2"/>
    </svg>`
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`)
}

function openChat() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    createWindow()
  }

  if (setupRequired) {
    openSetup()
    return
  }

  setupMode = false
  setWindowExpanded(false)
  enforceWindowSize()
  mainWindow.show()
  mainWindow.focus()
  mainWindow.webContents.send('open-chat')
  sendToPet('hide')
}

function showPet() {
  if (setupRequired) {
    openSetup()
    return
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('settings-force-close')
    setWindowExpanded(false)
    mainWindow.hide()
  }
  sendToPet('show')
}

function openSetup() {
  if (!mainWindow || mainWindow.isDestroyed()) createWindow()
  setupMode = true
  setWindowExpanded(true)
  setWindowMouseEventsIgnored(false)
  mainWindow.show()
  mainWindow.focus()
  mainWindow.webContents.send('setup-show', getSetupState())
}

function setWindowExpanded(expanded) {
  if (!mainWindow || mainWindow.isDestroyed() || settingsExpanded === expanded) return

  const currentBounds = mainWindow.getBounds()
  applyingWindowBounds = true

  if (expanded) {
    collapsedBounds = { ...currentBounds }
    settingsExpanded = true
    const workArea = screen.getDisplayMatching(currentBounds).workArea
    const overflow = Math.max(0, currentBounds.x + EXPANDED_SIZE.width - (workArea.x + workArea.width))
    const targetX = Math.max(workArea.x, currentBounds.x - overflow)
    mainWindow.setBounds({
      x: targetX,
      y: currentBounds.y,
      width: EXPANDED_SIZE.width,
      height: EXPANDED_SIZE.height
    })
  } else {
    settingsExpanded = false
    const target = collapsedBounds || currentBounds
    mainWindow.setBounds({
      x: target.x,
      y: target.y,
      width: COLLAPSED_SIZE.width,
      height: COLLAPSED_SIZE.height
    })
    collapsedBounds = null
  }

  setImmediate(() => { applyingWindowBounds = false })
}

function registerIpcHandlers() {
  ipcMain.on('window-drag', (_, delta = {}) => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    const deltaX = Number(delta.deltaX) || 0
    const deltaY = Number(delta.deltaY) || 0
    const [x, y] = mainWindow.getPosition()
    mainWindow.setPosition(x + deltaX, y + deltaY)
    enforceWindowSize()
  })

  ipcMain.on('mode-change', (_, mode) => {
    if (mode === 'pet') showPet()
    else openChat()
  })

  ipcMain.on('window-close', showPet)
  ipcMain.on('window-minimize', () => mainWindow?.minimize())
  ipcMain.on('window-hide', showPet)
  ipcMain.on('settings-expanded', (_, expanded) => setWindowExpanded(Boolean(expanded)))
  ipcMain.on('hit-regions:update', (_, regions = {}) => {
    hitRegions = {
      sprite: regions.sprite || hitRegions.sprite,
      historyOpen: Boolean(regions.historyOpen),
      settingsOpen: Boolean(regions.settingsOpen)
    }
  })
  ipcMain.handle('runtime-status:get', () => ({ ...runtimeStatus }))
  ipcMain.handle('setup:get', getSetupState)
  ipcMain.handle('setup:import-assets', async () => {
    const result = await selectAndImportAssets(mainWindow)
    setupRequired = !getSetupState().complete
    if (result.imported) {
      spriteAlphaMask = null
      loadSpriteAlphaMask()
    }
    return { ...result, setup: getSetupState() }
  })
  ipcMain.handle('setup:save-api-key', (_, apiKey) => {
    saveApiKey(apiKey)
    setAiConfigured(true)
    setupRequired = !getSetupState().complete
    return getSetupState()
  })
  ipcMain.handle('setup:complete', completeSetup)
  ipcMain.handle('config:get', getPublicConfig)
  ipcMain.handle('config:save-api-key', async (_, apiKey) => {
    saveApiKey(apiKey)
    setAiConfigured(true)
    await restartBackend()
    return getPublicConfig()
  })
  ipcMain.handle('assets:reimport', async () => {
    const result = await selectAndImportAssets(mainWindow)
    if (result.imported) {
      spriteAlphaMask = null
      loadSpriteAlphaMask()
      await Promise.all([restartBackend(), restartPet()])
    }
    return result
  })
  ipcMain.handle('knowledge:select-files', () => selectKnowledgeFiles(mainWindow))
  ipcMain.handle('knowledge:download-model', downloadEmbeddingModel)
  ipcMain.handle('knowledge:import-model', async () => {
    const result = await selectAndImportEmbeddingModel(mainWindow)
    if (result.imported) await restartBackend()
    return result
  })
  ipcMain.handle('pet-action', async (_, action) => {
    const normalized = typeof action === 'string' ? action.toUpperCase() : ''
    if (!ALLOWED_PET_ACTIONS.has(normalized)) return false
    return sendToPet(`action:${normalized}`)
  })
}

function getSetupState() {
  const assetsDirectory = resolveAssetsDirectory()
  const assets = validateAssetsDirectory(assetsDirectory)
  const config = getPublicConfig()
  return {
    complete: assets.valid && config.apiKeyConfigured,
    assetsReady: assets.valid,
    assetsDirectory,
    missingAssets: assets.missing,
    apiKeyConfigured: config.apiKeyConfigured,
    apiKeyHint: config.apiKeyHint,
    dataDirectory: config.dataDirectory
  }
}

async function completeSetup() {
  const state = getSetupState()
  if (!state.complete) throw new Error('资源与 DeepSeek API Key 尚未配置完成')

  setupRequired = false
  setupMode = false
  setWindowExpanded(false)
  spriteAlphaMask = null
  loadSpriteAlphaMask()
  mainWindow?.webContents.send('setup-complete', state)
  mainWindow?.hide()
  startRuntimeServices().catch(error => {
    console.error('[runtime] 初始化后启动失败:', error)
  })
  return state
}

function startPetSocketServer() {
  return new Promise((resolve, reject) => {
    petSocketServer = net.createServer(socket => {
      let buffer = ''
      socket.setEncoding('utf8')
      socket.on('data', chunk => {
        buffer += chunk
        const commands = buffer.split(/\r?\n/)
        buffer = commands.pop() || ''
        commands.map(command => command.trim()).filter(Boolean).forEach(handlePetCommand)
      })
      socket.on('end', () => {
        const command = buffer.trim()
        if (command) handlePetCommand(command)
      })
    })

    const handleStartupError = error => {
      console.error(`[pet-ipc] 无法监听 ${HOST}:${ELECTRON_PORT}:`, error.message)
      reject(error)
    }
    petSocketServer.once('error', handleStartupError)

    petSocketServer.listen(ELECTRON_PORT, HOST, () => {
      petSocketServer.removeListener('error', handleStartupError)
      petSocketServer.on('error', error => {
        console.error('[pet-ipc] 服务错误:', error.message)
        requestQuit()
      })
      console.log(`[pet-ipc] 监听 ${HOST}:${ELECTRON_PORT}`)
      resolve()
    })
  })
}

function handlePetCommand(command) {
  console.log('[pet-ipc] 收到:', command)
  if (command === 'open_chat') openChat()
}

async function startBackend() {
  if (shuttingDown || backendStarting) return
  backendStarting = true
  clearTimeout(backendRestartTimer)
  backendRestartTimer = null

  try {
    setRuntimeStatus('backend', 'starting')

    if (await isBackendRunning()) {
      markServiceReady('backend')
      return
    }

    const backendEntry = isDev
      ? path.join(projectRoot, 'backend/main.py')
      : resolveResourcePath('runtime/backend/kaltsit-backend.exe')
    if (!fs.existsSync(backendEntry)) {
      console.error('[backend] 运行入口不存在:', backendEntry)
      setRuntimeStatus('backend', 'error')
      return
    }

    const backendCommand = isDev
      ? resolveRuntimeCommand('KALTSIT_PYTHON', [], 'python')
      : backendEntry
    const backendArgs = isDev ? [backendEntry] : []
    const child = spawn(backendCommand, backendArgs, {
      cwd: path.dirname(backendEntry),
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        DEEPSEEK_API_KEY: getApiKey() || process.env.DEEPSEEK_API_KEY || '',
        KALTSIT_ASSETS_DIR: resolveAssetsDirectory(),
        KALTSIT_CONFIG_DIR: app.getPath('userData'),
        KALTSIT_DATA_DIR: app.getPath('userData'),
        PYTHONUNBUFFERED: '1'
      }
    })
    backendProcess = child

    pipeProcessOutput('backend', child)
    child.once('error', error => {
      console.error(`[backend] 无法启动 ${backendCommand}:`, error.message)
      if (backendProcess === child) backendProcess = null
      setRuntimeStatus('backend', 'error')
      scheduleBackendRestart()
    })
    child.once('exit', (code, signal) => {
      if (backendProcess === child) backendProcess = null
      if (shuttingDown) return
      if (backendRestartRequested) {
        backendRestartRequested = false
        setTimeout(startBackend, 120)
        return
      }
      console.error(`[backend] 意外退出 code=${code} signal=${signal}`)
      setRuntimeStatus('backend', 'error')
      scheduleBackendRestart()
    })

    const ready = await waitFor(
      isBackendRunning,
      45000,
      () => backendProcess !== child || child.exitCode !== null || child.killed
    )
    if (ready) {
      markServiceReady('backend')
    } else {
      terminateChild(child)
      setRuntimeStatus('backend', 'error')
      scheduleBackendRestart()
    }
  } finally {
    backendStarting = false
  }
}

async function startPet() {
  if (shuttingDown || petStarting) return
  petStarting = true
  clearTimeout(petRestartTimer)
  petRestartTimer = null

  try {
    setRuntimeStatus('pet', 'starting')

    if (await isPetRunning()) {
      markServiceReady('pet')
      return
    }

    const selectedJar = isDev
      ? path.join(projectRoot, 'kaltsit-pet/build/libs/kaltsit-pet-1.0.0.jar')
      : resolveResourcePath('kaltsit-pet/kaltsit-pet-1.0.0.jar')
    if (!fs.existsSync(selectedJar)) {
      console.error('[pet] JAR 不存在:', selectedJar)
      setRuntimeStatus('pet', 'error')
      return
    }

    const javaCommand = resolveRuntimeCommand(
      'KALTSIT_JAVA',
      ['runtime/java/bin/java.exe', 'java/bin/java.exe'],
      'java'
    )
    const child = spawn(javaCommand, ['-jar', selectedJar], {
      cwd: path.dirname(selectedJar),
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        KALTSIT_ASSETS_DIR: resolveAssetsDirectory(),
        KALTSIT_ELECTRON_EXE: process.execPath
      }
    })
    petProcess = child

    pipeProcessOutput('pet', child)
    child.once('error', error => {
      console.error(`[pet] 无法启动 ${javaCommand}:`, error.message)
      if (petProcess === child) petProcess = null
      setRuntimeStatus('pet', 'error')
      schedulePetRestart()
    })
    child.once('exit', (code, signal) => {
      if (petProcess === child) petProcess = null
      if (shuttingDown) return
      if (petRestartRequested) {
        petRestartRequested = false
        setTimeout(startPet, 120)
        return
      }
      console.error(`[pet] 意外退出 code=${code} signal=${signal}`)
      setRuntimeStatus('pet', 'error')
      schedulePetRestart()
    })

    const ready = await waitFor(
      isPetRunning,
      15000,
      () => petProcess !== child || child.exitCode !== null || child.killed
    )
    if (ready) {
      markServiceReady('pet')
    } else {
      terminateChild(child)
      setRuntimeStatus('pet', 'error')
      schedulePetRestart()
    }
  } finally {
    petStarting = false
  }
}

function scheduleBackendRestart() {
  clearTimeout(backendStabilityTimer)
  backendStabilityTimer = null
  if (shuttingDown || backendRestartTimer || backendRestartAttempts >= RESTART_LIMIT) return
  backendRestartAttempts += 1
  backendRestartTimer = setTimeout(() => {
    backendRestartTimer = null
    startBackend()
  }, 1500 * backendRestartAttempts)
}

async function restartBackend() {
  clearTimeout(backendRestartTimer)
  clearTimeout(backendStabilityTimer)
  backendRestartTimer = null
  backendStabilityTimer = null
  backendRestartAttempts = 0

  if (backendProcess) {
    backendRestartRequested = true
    terminateChild(backendProcess)
    return
  }
  if (!await isBackendRunning()) await startBackend()
}

function schedulePetRestart() {
  clearTimeout(petStabilityTimer)
  petStabilityTimer = null
  if (shuttingDown || petRestartTimer || petRestartAttempts >= RESTART_LIMIT) return
  petRestartAttempts += 1
  petRestartTimer = setTimeout(() => {
    petRestartTimer = null
    startPet()
  }, 1500 * petRestartAttempts)
}

async function restartPet() {
  clearTimeout(petRestartTimer)
  clearTimeout(petStabilityTimer)
  petRestartTimer = null
  petStabilityTimer = null
  petRestartAttempts = 0

  if (petProcess) {
    petRestartRequested = true
    terminateChild(petProcess)
    return
  }
  if (!await isPetRunning()) await startPet()
}

function resolveResourcePath(relativePath) {
  return isDev
    ? path.join(projectRoot, relativePath)
    : path.join(process.resourcesPath, relativePath)
}

function resolveRuntimeCommand(environmentName, relativeCandidates, fallback) {
  const configured = process.env[environmentName]?.trim()
  if (configured) return configured

  for (const relativePath of relativeCandidates) {
    const candidate = resolveResourcePath(relativePath)
    if (fs.existsSync(candidate)) return candidate
  }
  return fallback
}

function resolveAssetsDirectory() {
  const configured = process.env.KALTSIT_ASSETS_DIR?.trim()
  if (configured) return path.resolve(configured)

  const candidates = isDev
    ? [path.join(projectRoot, 'assets')]
    : [path.join(app.getPath('userData'), 'assets'), path.join(process.resourcesPath, 'assets')]
  return candidates.find(candidate => fs.existsSync(candidate)) || candidates[0]
}

function pipeProcessOutput(name, child) {
  child.stdout?.on('data', data => console.log(`[${name}]`, data.toString().trimEnd()))
  child.stderr?.on('data', data => console.error(`[${name}]`, data.toString().trimEnd()))
}

function isBackendRunning() {
  return new Promise(resolve => {
    let body = ''
    const request = http.get(`http://${HOST}:${BACKEND_PORT}/health`, response => {
      response.setEncoding('utf8')
      response.on('data', chunk => { body += chunk })
      response.on('end', () => {
        try {
          const health = JSON.parse(body)
          const isExpectedService =
            response.statusCode >= 200 && response.statusCode < 300 &&
            health.service === 'kaltsit-backend' && health.status === 'ok'
          if (isExpectedService) setAiConfigured(Boolean(health.configured))
          resolve(isExpectedService)
        } catch {
          resolve(false)
        }
      })
    })
    request.setTimeout(900, () => {
      request.destroy()
      resolve(false)
    })
    request.on('error', () => resolve(false))
  })
}

function isPetRunning() {
  return new Promise(resolve => {
    const socket = net.createConnection({ host: HOST, port: PET_PORT })
    let settled = false
    let response = ''
    const finish = result => {
      if (settled) return
      settled = true
      socket.removeAllListeners()
      socket.destroy()
      resolve(result)
    }
    socket.setEncoding('utf8')
    socket.setTimeout(900)
    socket.once('connect', () => socket.write('ping\n'))
    socket.on('data', data => {
      response += data
      if (response.trim() === 'kaltsit-pet') finish(true)
    })
    socket.once('end', () => finish(false))
    socket.once('timeout', () => finish(false))
    socket.once('error', () => finish(false))
  })
}

async function waitFor(check, timeoutMs, shouldAbort = () => false) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (shouldAbort()) return false
    if (await check()) return true
    await delay(250)
  }
  return false
}

function markServiceReady(service) {
  setRuntimeStatus(service, 'ready')
  if (service === 'backend') {
    backendMonitorFailures = 0
    if (backendRestartAttempts > 0 && !backendStabilityTimer) {
      backendStabilityTimer = setTimeout(() => {
        backendRestartAttempts = 0
        backendStabilityTimer = null
      }, RESTART_STABLE_MS)
    }
    return
  }

  petMonitorFailures = 0
  if (petRestartAttempts > 0 && !petStabilityTimer) {
    petStabilityTimer = setTimeout(() => {
      petRestartAttempts = 0
      petStabilityTimer = null
    }, RESTART_STABLE_MS)
  }
}

function startRuntimeMonitoring() {
  clearInterval(runtimeMonitorTimer)
  runtimeMonitorTimer = setInterval(monitorRuntime, RUNTIME_MONITOR_MS)
}

async function monitorRuntime() {
  if (shuttingDown || runtimeMonitorRunning) return
  runtimeMonitorRunning = true
  try {
    const [backendReady, petReady] = await Promise.all([
      isBackendRunning(),
      isPetRunning()
    ])

    if (backendReady) {
      backendMonitorFailures = 0
      if (runtimeStatus.backend !== 'ready') markServiceReady('backend')
    } else if (!backendStarting) {
      backendMonitorFailures += 1
      if (backendMonitorFailures >= 2) {
        setRuntimeStatus('backend', 'error')
        terminateChild(backendProcess)
        scheduleBackendRestart()
      }
    }

    if (petReady) {
      petMonitorFailures = 0
      if (runtimeStatus.pet !== 'ready') markServiceReady('pet')
    } else if (!petStarting) {
      petMonitorFailures += 1
      if (petMonitorFailures >= 2) {
        setRuntimeStatus('pet', 'error')
        terminateChild(petProcess)
        schedulePetRestart()
      }
    }
  } finally {
    runtimeMonitorRunning = false
  }
}

function sendToPet(command) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: HOST, port: PET_PORT })
    socket.setTimeout(700)
    socket.once('connect', () => {
      socket.end(`${command}\n`)
      resolve()
    })
    socket.once('timeout', () => {
      socket.destroy()
      reject(new Error('桌宠通信超时'))
    })
    socket.once('error', reject)
  }).then(() => true).catch(() => false)
}

function setRuntimeStatus(service, status) {
  if (runtimeStatus[service] === status) return
  runtimeStatus[service] = status
  broadcastRuntimeStatus()
}

function setAiConfigured(configured) {
  if (runtimeStatus.aiConfigured === configured) return
  runtimeStatus.aiConfigured = configured
  broadcastRuntimeStatus()
}

function broadcastRuntimeStatus() {
  if (!mainWindow || mainWindow.isDestroyed() || mainWindow.webContents.isLoading()) return
  mainWindow.webContents.send('runtime-status', { ...runtimeStatus })
}

async function requestQuit() {
  if (shuttingDown) return
  shuttingDown = true
  clearRestartTimers()
  await sendToPet('quit')
  await delay(120)
  app.quit()
}

function cleanupRuntime() {
  shuttingDown = true
  clearRestartTimers()
  petSocketServer?.close()
  tray?.destroy()
  clearInterval(mouseHitTestTimer)
  clearInterval(runtimeMonitorTimer)
  clearTimeout(backendStabilityTimer)
  clearTimeout(petStabilityTimer)
  terminateChild(backendProcess)
  terminateChild(petProcess)
}

function loadSpriteAlphaMask() {
  const spritePath = path.join(resolveAssetsDirectory(), 'illustration', SPRITE_FILENAME)
  if (!fs.existsSync(spritePath)) return

  const image = nativeImage.createFromPath(spritePath)
  if (image.isEmpty()) return
  const size = image.getSize()
  spriteAlphaMask = {
    width: size.width,
    height: size.height,
    pixels: image.toBitmap()
  }
}

function startMouseHitTesting() {
  clearInterval(mouseHitTestTimer)
  mouseHitTestTimer = setInterval(updateMouseHitTest, 50)
}

function updateMouseHitTest() {
  if (!mainWindow || mainWindow.isDestroyed() || !mainWindow.isVisible()) return
  if (setupMode) {
    setWindowMouseEventsIgnored(false)
    return
  }
  const cursor = screen.getCursorScreenPoint()
  const bounds = mainWindow.getBounds()
  const point = { x: cursor.x - bounds.x, y: cursor.y - bounds.y }
  const insideWindow = point.x >= 0 && point.y >= 0 && point.x < bounds.width && point.y < bounds.height
  const interactive = insideWindow && (
    isPointInRect(point, { x: 12, y: 528, width: 476, height: 160 }) ||
    (hitRegions.historyOpen && isPointInRect(point, { x: 12, y: 386, width: 476, height: 144 })) ||
    (hitRegions.settingsOpen && isPointInRect(point, { x: 512, y: 12, width: 336, height: 676 })) ||
    isOpaqueSpritePoint(point)
  )
  setWindowMouseEventsIgnored(!interactive)
}

function isPointInRect(point, rect) {
  return point.x >= rect.x && point.y >= rect.y &&
    point.x < rect.x + rect.width && point.y < rect.y + rect.height
}

function isOpaqueSpritePoint(point) {
  const sprite = hitRegions.sprite
  if (!sprite || !isPointInRect(point, sprite)) return false
  if (!spriteAlphaMask) return true

  const sampleX = Math.max(0, Math.min(
    spriteAlphaMask.width - 1,
    Math.floor((point.x - sprite.x) / sprite.width * spriteAlphaMask.width)
  ))
  const sampleY = Math.max(0, Math.min(
    spriteAlphaMask.height - 1,
    Math.floor((point.y - sprite.y) / sprite.height * spriteAlphaMask.height)
  ))
  const alphaOffset = (sampleY * spriteAlphaMask.width + sampleX) * 4 + 3
  return spriteAlphaMask.pixels[alphaOffset] > 18
}

function setWindowMouseEventsIgnored(shouldIgnore) {
  if (!mainWindow || mainWindow.isDestroyed() || mouseEventsIgnored === shouldIgnore) return
  mouseEventsIgnored = shouldIgnore
  if (shouldIgnore) mainWindow.setIgnoreMouseEvents(true, { forward: true })
  else mainWindow.setIgnoreMouseEvents(false)
}

function clearRestartTimers() {
  clearTimeout(backendRestartTimer)
  clearTimeout(petRestartTimer)
  backendRestartTimer = null
  petRestartTimer = null
}

function terminateChild(child) {
  if (!child || child.killed || !child.pid) return
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
      windowsHide: true,
      stdio: 'ignore'
    })
    return
  }
  child.kill()
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
