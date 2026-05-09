# ADB / Fastboot GUI Tool 📱

這是一個基於 **Electron** 與 **Python (Flask)** 開發的輕量化 Android 裝置管理工具。它將複雜的 ADB 與 Fastboot 命令列操作轉化為直覺的圖形化介面，並內建了即時終端機串流功能，告別純文字命令列，提供現代化的深色主題 UI 與內建終端機（Console）介面。

## 🛠️ 技術架構

本專案採用「前後端分離」並以 Electron 封裝的混合模式：

* **主進程 (Electron)**：負責啟動 Flask 伺服器、管理視窗生命週期、呼叫系統檔案對話框、處理進程清理。
* **後端服務 (Python Flask)**：本機微型伺服器 (預設運行於 Port `54321`)，負責執行子程序 (`subprocess`) 並與 Android SDK 工具 (`adb.exe`, `fastboot.exe`) 互動。
* **前端渲染層 (HTML/JS/CSS)**：無框架的原生前端實作，使用 JetBrains Mono 字體與 Tabler Icons，負責與 Flask API 互動並彩現終端機畫面。

## 🚀 快速開始

### 1. 環境準備

* 安裝 [Node.js](https://nodejs.org/) (用於執行 Electron)。
* 安裝 [Python 3.x](https://www.python.org/) (用於執行 Flask 後端)。
* 下載 [Android SDK Platform-Tools](https://developer.android.com/studio/releases/platform-tools) 並解壓縮，確保 `platform-tools` 資料夾與 `main.js` 在同一目錄下。

### 2. 安裝與執行

1. **複製倉庫**

   ```bash
   git clone https://github.com/QwQCat-jpg147/Vision-ADB.git
   cd Vision-ADB
   ```

2. **安裝 Python 依賴**

   ```bash
   pip install -r requirements.txt
   ```

3. **安裝 Node.js 依賴**

   ```bash
   npm install
   ```

4. **啟動應用程式**

   ```bash
   npm start
   ```

## 📦 打包說明 (Windows)

本專案已支援生產環境與開發環境的路徑自動切換。若要打包為 Windows 執行檔 (`.exe`)：

1. **打包 Python 後端**：
   先使用 PyInstaller 將 `server.py` 打包成獨立的可執行檔。

   ```bash
   pyinstaller --onefile --noconsole server.py
   ```

2. **打包 Electron**：
   使用 Electron Builder 等工具進行打包。

   > **注意**：確認將打包好的 `server.exe` 與 `platform-tools` 資料夾配置到 `package.json` 中的 `extraResources` 下。

## ⚖️ 開源許可

本專案採用 [MIT License](LICENSE) 進行許可。

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request 來改進這個工具！
