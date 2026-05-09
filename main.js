const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');

let win = null;
let serverProcess = null;
const PORT = 54321;

// ── 1. 路径处理中心 ─────────────────────────────────────────
const getPaths = () => {
  const isPackaged = app.isPackaged;
  return {
    // 后端执行文件路径
    server: isPackaged 
      ? path.join(process.resourcesPath, 'server.exe')
      : path.join(__dirname, '..', 'server.py'),
    // ADB 执行文件路径
    adb: isPackaged
      ? path.join(process.resourcesPath, 'platform-tools', 'adb.exe')
      : path.join(__dirname, '..', 'platform-tools', 'adb.exe'),
    // 工作目录（确保后端能找到旁边的资源）
    cwd: isPackaged ? process.resourcesPath : path.join(__dirname, '..')
  };
};

// ── 2. 启动后端 Flask Server ────────────────────────────────
function startServer() {
  const paths = getPaths();
  console.log('[Main] 启动路径:', paths.server);

  if (app.isPackaged) {
    // 生产环境：运行打包好的 server.exe
    serverProcess = spawn(paths.server, [], { 
      windowsHide: true, 
      cwd: paths.cwd 
    });
  } else {
    // 开发环境：通过 python 运行 server.py
    serverProcess = spawn('python', [paths.server], { 
      windowsHide: false, 
      cwd: paths.cwd 
    });
  }

  serverProcess.stdout.on('data', d => console.log('[Server]', d.toString().trim()));
  serverProcess.stderr.on('data', d => console.error('[Server ERR]', d.toString().trim()));
}

// ── 3. 轮询检查后端是否就绪 ──────────────────────────────────
function waitForServer(callback) {
  const check = () => {
    http.get(`http://127.0.0.1:${PORT}/api/check`, (res) => {
      console.log('[Main] 后端已就绪');
      callback();
    }).on('error', () => {
      console.log('[Main] 等待后端启动...');
      setTimeout(check, 500);
    });
  };
  check();
}

// ── 4. 窗口创建 ─────────────────────────────────────────────
function createWindow() {
  win = new BrowserWindow({
    width: 900,
    height: 600,
    minWidth: 900,
    minHeight: 600,
    frame: true, // 🌟 使用原生邊框，穩定且可靠！
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
    win.once('ready-to-show', () => win.show());
  });

  win.on('closed', () => { win = null; });
}

// ── 5. 进程清理逻辑 (解决 ADB 关不掉的问题) ────────────────────
function cleanup() {
  const paths = getPaths();
  console.log('[Main] 正在执行退出清理...');

  // 1. 杀死 ADB Server (关键！)
  try {
    // 使用 execSync 确保在主进程退出前完成
    execSync(`"${paths.adb}" kill-server`);
    console.log('[Main] ADB Server 已关闭');
  } catch (e) {
    console.log('[Main] ADB 关闭跳过或失败');
  }

  // 2. 杀死 Flask 后端
  if (serverProcess) {
    if (process.platform === 'win32') {
      spawn("taskkill", ["/pid", serverProcess.pid, '/f', '/t']);
    } else {
      serverProcess.kill('SIGTERM');
    }
  }
}

// ── 6. App 生命周期 ─────────────────────────────────────────
app.whenReady().then(() => {
  startServer();
  createWindow();
});

app.on('will-quit', cleanup);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ── 7. IPC 窗口控制 ──────────────────────────────────────────
ipcMain.on('win-close', () => win?.close());
ipcMain.on('win-minimize', () => win?.minimize());
ipcMain.on('win-maximize', () => {
  if (win?.isMaximized()) win.unmaximize();
  else win?.maximize();
});