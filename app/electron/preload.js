const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  dragWindow:    (delta) => ipcRenderer.send('window-drag', delta),
  closeWindow:   () => ipcRenderer.send('window-close'),
  minimizeWindow:() => ipcRenderer.send('window-minimize'),
  hideWindow:    () => ipcRenderer.send('window-hide'),
  setMode:       (mode) => ipcRenderer.send('mode-change', mode),
  showPetMenu:   () => ipcRenderer.send('pet-context-menu'),
  onOpenChat:    (cb) => ipcRenderer.on('open-chat', cb),
})
