const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let win = null;
let serverProcess = null;
const PORT = 54321;

// ── 判斷後端執行路徑 ────────────────────────────────
function getServerPath() {
  // 打包後找 server.exe，開發時找 server.py
  return app.isPackaged
    ? path.join(process.resourcesPath, 'server.exe')
    : path.join(__dirname, 'server.py'); 
}

// ── 啟動 Flask server ────────────────────────────────
function startServer() {
  const serverPath = getServerPath();
  
  if (app.isPackaged) {
    serverProcess = spawn(serverPath, [], { windowsHide: true });
  } else {
    // 開發環境：直接透過 python 執行
    serverProcess = spawn('python', [serverPath], { windowsHide: true });
  }

  serverProcess.stdout.on('data', d => console.log('[srv]', d.toString().trim()));
  serverProcess.stderr.on('data', d => console.log('[srv] ERR:', d.toString().trim()));
  serverProcess.on('exit', code => console.log('[srv] exited with code', code));
}

// ── 輪詢等 Flask 就緒 ───────────
function waitForServer(callback, retries = 30) {
  http.get(`http://127.0.0.1:${PORT}/api/check`, () => {
    callback();
  }).on('error', () => {
    if (retries > 0) {
      setTimeout(() => waitForServer(callback, retries - 1), 500);
    } else {
      console.error('後端伺服器啟動失敗，請檢查 Port 是否被佔用');
    }
  });
}

// ── 建立視窗 ─────────────────────────────────────────
function createWindow() {
  win = new BrowserWindow({
    width: 900,
    height: 600,
    minWidth: 800,
    minHeight: 580,
    frame: false, // 無邊框
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    trafficLightPosition: { x: 16, y: 12 },
    backgroundColor: '#0d1117',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  waitForServer(() => {
    win.loadURL(`http://127.0.0.1:${PORT}`);
  });

  win.once('ready-to-show', () => win.show());
  win.on('closed', () => { win = null; });
}

// ── 監聽前端 (index.html) 傳來的視窗控制事件 ───────────
ipcMain.on('win-close', (event) => {
  const webWindow = BrowserWindow.fromWebContents(event.sender);
  if (webWindow) webWindow.close();
});
ipcMain.on('win-minimize', (event) => {
  const webWindow = BrowserWindow.fromWebContents(event.sender);
  if (webWindow) webWindow.minimize();
});
ipcMain.on('win-maximize', (event) => {
  const webWindow = BrowserWindow.fromWebContents(event.sender);
  if (webWindow) {
    if (webWindow.isMaximized()) webWindow.unmaximize();
    else webWindow.maximize();
  }
});

// ── App 生命週期 ─────────────────────────────────────
app.whenReady().then(() => {
  startServer();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// 【核心修復】：App 準備退出時，強制殺死 Python 服務器，防止覆蓋安裝報錯！
app.on('will-quit', () => {
  if (serverProcess) {
    if (process.platform === 'win32') {
      spawn("taskkill", ["/pid", serverProcess.pid, '/f', '/t']);
    } else {
      serverProcess.kill('SIGTERM');
    }
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
