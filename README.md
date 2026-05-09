# 📱 ADB / Fastboot 視覺化刷機工具

這是一款基於 **Electron** 與 **Python Flask** 開發的跨平台安卓設備工具箱。透過簡潔的網頁介面，封裝了複雜的 ADB 與 Fastboot 指令，讓刷機、Sideload 與設備管理變得更直覺、更安全。

## ✨ 核心特色

- 🚀 **視覺化終端**：實時串流 (SSE) 指令輸出，像是在用真終端一樣。
- 🛡️ **安全路徑防護**：自動偵測刷機包路徑，防止因「中文路徑」導致 ADB 異常中斷。
- 🎯 **一鍵操作**：支援分區閃刷、Sideload 刷入、設備重啟至 Recovery/Bootloader 等常用功能。
- 🎨 **現代化介面**：採用深色系透明無邊框設計，符合極客審美。

## 🛠️ 技術架構

- **前端**: HTML5, CSS3 (CSS Variables), JavaScript
- **框架**: [Electron](https://www.electronjs.org/)
- **後端**: [Flask](https://flask.palletsprojects.com/) (Python)
- **通訊**: IPC (Electron <-> Renderer) & REST API / SSE (Electron <-> Flask)

## 📦 如何在開發環境執行

### 前提條件
- [Node.js](https://nodejs.org/) (建議 v18 以上)
- [Python 3.x](https://www.python.org/)

### 步驟
1. **複製專案**
   ```bash
   git clone [https://github.com/QwQCat-jpg147/Vision-ADB.git](https://github.com/QwQCat-jpg147/Vision-ADB.git)
   cd Vision-ADB
   ```
   (readme by ai)
