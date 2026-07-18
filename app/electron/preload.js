const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  dragWindow: delta => ipcRenderer.send('window-drag', delta),
  closeWindow: () => ipcRenderer.send('window-close'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  hideWindow: () => ipcRenderer.send('window-hide'),
  setMode: mode => ipcRenderer.send('mode-change', mode),
  setSettingsExpanded: expanded => ipcRenderer.send('settings-expanded', expanded),
  setPetLipSync: level => ipcRenderer.send('pet-lipsync', level),
  updateHitRegions: regions => ipcRenderer.send('hit-regions:update', regions),
  getRuntimeStatus: () => ipcRenderer.invoke('runtime-status:get'),
  getLocalApiToken: () => ipcRenderer.invoke('runtime-token:get'),
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
  downloadVoiceRecognitionModel: () => ipcRenderer.invoke('voice:download-asr-model'),
  importVoiceRecognitionModel: () => ipcRenderer.invoke('voice:import-asr-model'),
  triggerPetAction: action => ipcRenderer.invoke('pet-action', action),
  triggerPetBehavior: behavior => ipcRenderer.invoke('pet-behavior', behavior),
  getDesktopToolState: () => ipcRenderer.invoke('tools:get-state'),
  setDesktopToolPermission: (permission, enabled) => ipcRenderer.invoke('tools:set-permission', permission, enabled),
  readClipboardText: () => ipcRenderer.invoke('tools:read-clipboard'),
  selectDesktopTextFile: () => ipcRenderer.invoke('tools:select-file'),
  chooseDesktopSearchRoot: () => ipcRenderer.invoke('tools:choose-search-root'),
  searchDesktopFiles: query => ipcRenderer.invoke('tools:search-files', query),
  showDesktopSearchResult: relativePath => ipcRenderer.invoke('tools:show-search-result', relativePath),
  capturePrimaryScreen: () => ipcRenderer.invoke('tools:capture-screen'),
  getUpdateState: () => ipcRenderer.invoke('updates:get-state'),
  checkForUpdates: () => ipcRenderer.invoke('updates:check'),
  downloadUpdate: () => ipcRenderer.invoke('updates:download'),
  installUpdate: () => ipcRenderer.invoke('updates:install'),
  getDiagnostics: () => ipcRenderer.invoke('diagnostics:get'),
  exportDiagnostics: () => ipcRenderer.invoke('diagnostics:export'),
  restartRuntimeService: service => ipcRenderer.invoke('diagnostics:restart-service', service),
  setSafeMode: enabled => ipcRenderer.invoke('diagnostics:set-safe-mode', enabled),
  listDatabaseBackups: () => ipcRenderer.invoke('diagnostics:list-backups'),
  createDatabaseBackup: () => ipcRenderer.invoke('diagnostics:create-backup'),
  restoreDatabaseBackup: filename => ipcRenderer.invoke('diagnostics:restore-backup', filename),
  onOpenChat: callback => subscribe('open-chat', callback),
  onRuntimeStatus: callback => subscribe('runtime-status', callback),
  onForceCloseSettings: callback => subscribe('settings-force-close', callback),
  onShowSetup: callback => subscribe('setup-show', callback),
  onSetupComplete: callback => subscribe('setup-complete', callback),
  onUpdateStatus: callback => subscribe('update-status', callback)
})

function subscribe(channel, callback) {
  const listener = (_, payload) => callback(payload)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}
