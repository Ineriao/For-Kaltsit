const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  dragWindow: delta => ipcRenderer.send('window-drag', delta),
  closeWindow: () => ipcRenderer.send('window-close'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  hideWindow: () => ipcRenderer.send('window-hide'),
  setMode: mode => ipcRenderer.send('mode-change', mode),
  setSettingsExpanded: expanded => ipcRenderer.send('settings-expanded', expanded),
  updateHitRegions: regions => ipcRenderer.send('hit-regions:update', regions),
  getRuntimeStatus: () => ipcRenderer.invoke('runtime-status:get'),
  getSetupState: () => ipcRenderer.invoke('setup:get'),
  importAssets: () => ipcRenderer.invoke('setup:import-assets'),
  saveSetupApiKey: apiKey => ipcRenderer.invoke('setup:save-api-key', apiKey),
  completeSetup: () => ipcRenderer.invoke('setup:complete'),
  getSecureConfig: () => ipcRenderer.invoke('config:get'),
  saveApiKey: apiKey => ipcRenderer.invoke('config:save-api-key', apiKey),
  reimportAssets: () => ipcRenderer.invoke('assets:reimport'),
  selectKnowledgeFiles: () => ipcRenderer.invoke('knowledge:select-files'),
  downloadEmbeddingModel: () => ipcRenderer.invoke('knowledge:download-model'),
  importEmbeddingModel: () => ipcRenderer.invoke('knowledge:import-model'),
  triggerPetAction: action => ipcRenderer.invoke('pet-action', action),
  onOpenChat: callback => subscribe('open-chat', callback),
  onRuntimeStatus: callback => subscribe('runtime-status', callback),
  onForceCloseSettings: callback => subscribe('settings-force-close', callback),
  onShowSetup: callback => subscribe('setup-show', callback),
  onSetupComplete: callback => subscribe('setup-complete', callback)
})

function subscribe(channel, callback) {
  const listener = (_, payload) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}
