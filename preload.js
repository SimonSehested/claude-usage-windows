const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('claude', {
  onData: (cb) => {
    ipcRenderer.on('usage-data', (_event, data) => cb(data));
  },
  reportHeight: (h) => {
    ipcRenderer.send('window-height', h);
  },
  close: () => {
    ipcRenderer.send('close-window');
  },
});
