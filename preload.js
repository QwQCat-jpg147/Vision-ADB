const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  closeWindow:    () => ipcRenderer.send('win-close'),
  minimizeWindow: () => ipcRenderer.send('win-minimize'),
  maximizeWindow: () => ipcRenderer.send('win-maximize'),
  isElectron: true,
  getPlatform: () => Promise.resolve(process.platform),
  openFileDialog: () => ipcRenderer.invoke('dialog:openFile'),
  openZipDialog: () => ipcRenderer.invoke('dialog:openZip'),
});