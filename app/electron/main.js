const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

const ASSET_BASE = path.join(__dirname, '../..')
const SPRITE_PATH = path.join(ASSET_BASE, '立绘_凯尔希·思衡托_1.png')

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged
let mainWindow
let tray
let backendProcess

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 500,
    height: 700,
    useContentSize: true,
    minWidth: 500,
    maxWidth: 500,
    minHeight: 700,
    maxHeight: 700,
    frame: false,
    transparent: true,
    resizable: false,
    center: true,
    alwaysOnTop: false,
    skipTaskbar: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // 注入立绘路径到渲染进程
  mainWindow.webContents.on('dom-ready', () => {
    if (fs.existsSync(SPRITE_PATH)) {
      const spriteData = fs.readFileSync(SPRITE_PATH).toString('base64')
      mainWindow.webContents.executeJavaScript(
        `window.__KALTSIT_SPRITE__ = "data:image/png;base64,${spriteData}";`
      )
    }
  })

  mainWindow.on('closed', () => { mainWindow = null })

  // 防止任何原因导致窗口扩张
  mainWindow.on('resize', () => {
    const [w, h] = mainWindow.getContentSize()
    if (w !== 500 || h !== 700) mainWindow.setContentSize(500, 700)
  })
}

const http = require('http')

function isBackendRunning() {
  return new Promise(resolve => {
    const req = http.get('http://127.0.0.1:8765/health', () => resolve(true))
    req.on('error', () => resolve(false))
    req.setTimeout(1000, () => { req.destroy(); resolve(false) })
  })
}

async function startBackend() {
  if (await isBackendRunning()) {
    console.log('[backend] 已在运行，跳过启动')
    return
  }
  const backendPath = path.join(__dirname, '../../backend/main.py')
  backendProcess = spawn('python', [backendPath], {
    stdio: 'pipe',
    env: { ...process.env }
  })
  backendProcess.stdout.on('data', d => console.log('[backend]', d.toString()))
  backendProcess.stderr.on('data', d => console.error('[backend]', d.toString()))
}

function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, '../public/tray.png'))
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon)
  const menu = Menu.buildFromTemplate([
    { label: '显示', click: () => mainWindow?.show() },
    { label: '隐藏', click: () => mainWindow?.hide() },
    { type: 'separator' },
    { label: '退出', click: () => app.quit() }
  ])
  tray.setToolTip('凯尔希')
  tray.setContextMenu(menu)
  tray.on('click', () => {
    if (mainWindow?.isVisible()) mainWindow.hide()
    else mainWindow?.show()
  })
}

app.whenReady().then(async () => {
  await startBackend()
  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  backendProcess?.kill()
})

// 窗口拖拽：改用原生 startDragging，零延迟
ipcMain.on('window-drag-start', () => {
  mainWindow?.moveTop()
})

ipcMain.on('window-drag', (_, { deltaX, deltaY }) => {
  if (!mainWindow) return
  const [x, y] = mainWindow.getPosition()
  mainWindow.setPosition(x + deltaX, y + deltaY)
  mainWindow.setContentSize(500, 700)
})

// 模式切换：chat ↔ pet
ipcMain.on('mode-change', (_, mode) => {
  if (!mainWindow) return
  if (mode === 'pet') {
    mainWindow.setContentSize(800, 800)
    mainWindow.setAlwaysOnTop(true)
    mainWindow.setResizable(false)
  } else {
    mainWindow.setContentSize(500, 700)
    mainWindow.setAlwaysOnTop(false)
    mainWindow.setResizable(false)
  }
})

ipcMain.on('window-close', () => app.quit())
ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-hide', () => mainWindow?.hide())

// 桌宠右键菜单
ipcMain.on('pet-context-menu', () => {
  if (!mainWindow) return
  const menu = Menu.buildFromTemplate([
    {
      label: '展开对话',
      click: () => {
        mainWindow.setContentSize(500, 700)
        mainWindow.setAlwaysOnTop(false)
        mainWindow.webContents.send('open-chat')
      }
    },
    { type: 'separator' },
    {
      label: '最小化',
      click: () => mainWindow.minimize()
    },
    {
      label: '退出',
      click: () => app.quit()
    },
  ])
  menu.popup({ window: mainWindow })
})
