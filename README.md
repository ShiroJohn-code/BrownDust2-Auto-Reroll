# 🎮 無限抽自動化程式 (Infinite Gacha Automation)

基於 Python 開發的高效能自動抽卡輔助工具，採用 **MVC 架構**，整合 **FastAPI Web 控制台**、**Telegram 遠端互動控制** 以及 **ADB 極速通訊**。

支援三種操作模式：**純本機熱鍵**、**Web 網頁控制台**、**Telegram Bot 遠端操控**，可自由組合。

---

## ✨ 主要功能

### 🖥️ 雙平台自動化
- **Windows 桌面模式** — `mss` 毫秒級截圖 + `ctypes` 底層滑鼠驅動
- **模擬器模式 (LDPlayer)** — `pure-python-adb` Socket 直連，自動偵測模擬器進程與 ADB 路徑

### 📱 Telegram Bot 遠端控制
- **一鍵開始/暫停** — 自動判斷狀態的切換按鈕
- **📊 統計總覽** — 運行狀態、抽卡統計、五星分布一頁看完
- **⚙️ 門檻設定** — 直接用 ➕➖ 按鈕即時調整 5星/4星門檻
- **🗑️ 重置數據** — 一鍵清除所有抽卡紀錄，從零開始
- **達標通知** — 自動截圖 + 互動式繼續/停止按鈕，永遠只保留最新一個對話框
- **Web UI 快捷連結** — 自動判斷 WebUI 是否啟用，動態顯示內網/外網按鈕

### 🌐 Web 控制台
- 即時監控畫面 (MJPEG Stream)
- 動態調整抽卡門檻
- 密碼保護登入 + IP 封鎖機制 (3 次錯誤鎖定 1 小時)
- 可透過 `config.ini` 開關及自訂連接埠

### 🛡️ 穩定健壯
- **智慧啟動器 (`Run.py`)** — 自動安裝依賴、取得管理員權限、攔截崩潰錯誤
- **日誌管理** — 自動輪替 (2MB/檔, 保留 5 份)，過濾網路庫雜訊
- **執行緒安全** — `mss` 獨立實例 + `frame_lock` 防止畫面撕裂

---

## 📂 專案架構

```text
無限抽_2K/
├── Run.py                    # 🚀 智慧啟動器 (入口點)
├── main.py                   # 🧠 核心主程式 (MVC 架構)
├── config.ini                # ⚙️ 設定檔
├── requirements.txt          # 📦 依賴套件清單
│
├── mod/                      # 🔧 功能模組
│   ├── image_processor.py    #    OpenCV 圖像處理、星級分析
│   ├── input_handler.py      #    滑鼠/觸控操作封裝
│   ├── ld_controller.py      #    ADB Socket 通訊層
│   ├── web_ui.py             #    FastAPI Web 控制台 + 認證
│   ├── telegram_bot.py       #    Telegram Bot 互動控制器
│   └── character_detector.py #    角色特徵比對辨識
│
├── templates/                # 🎨 Web 前端 (Bootstrap 5)
│   └── index.html
├── logs/                     # 📝 系統日誌
└── mouse/                    # 🖼️ 辨識用圖片資源
```

---

## 🚀 快速開始

### 環境需求

- **Windows 10/11**
- **Python 3.10+**

### 啟動

直接雙擊 **`Run.py`** 即可，程式會自動：
1. 檢查並安裝缺少的套件
2. 請求系統管理員權限
3. 啟動自動化程式

### ⚙️ 設定檔 (`config.ini`)

```ini
[Telegram]
token =                  # Telegram Bot Token (留空 = 不啟用)
chat_id =                # Telegram Chat ID

[Emulator]
adb_path =               # ADB 路徑 (留空 = 自動偵測，找不到則用 Windows 模式)

[Thresholds]
min_5star = 1            # 5星達標門檻
min_4star = 0            # 4星達標門檻
min_score = 0            # 分數達標門檻

[System]
monitor_index = 1        # 截圖用螢幕編號

[WebUI]
enabled = true           # Web 控制台開關 (true/false)
port = 8964              # Web 控制台連接埠
password = admin         # Web 控制台登入密碼
```

### 操作模式

| 設定 | 行為 |
|------|------|
| Telegram ✅ WebUI ✅ | 完整功能：遠端 Bot + 網頁控制台 + 熱鍵 |
| Telegram ✅ WebUI ❌ | 純 Bot 遠端控制 + 熱鍵 (不含內外網按鈕) |
| Telegram ❌ WebUI ✅ | 網頁控制台 + 熱鍵 |
| Telegram ❌ WebUI ❌ | 純本機熱鍵操作 |

### ⌨️ 熱鍵

| 按鍵 | 功能 |
|------|------|
| `F5` | 啟動 / 暫停自動抽卡 |
| `F9` | 單次截圖分析 (Debug) |
| `F10` | 顯示五星分布統計 |
| `F12` | 顯示抽卡統計摘要 |

---

## 🛠️ 技術細節

1. **截圖效能** — Windows 模式使用 `mss`，每次截圖建立獨立實例確保執行緒安全
2. **ADB 通訊** — 透過 `pure-python-adb` Socket 長連線 (Port 5037) 取代 `subprocess` 指令，毫秒級響應
3. **Web 認證** — 純 ASGI 中間件 + Cookie Session + IP 封鎖，不依賴 `BaseHTTPMiddleware` 避免 Request Body 消耗問題
4. **Telegram 訊息管理** — 追蹤 `last_notification_message_id`，新通知前自動刪除舊對話框，先發圖再發按鈕確保互動框在最底部

---

## 📅 版本紀錄

### v2.0.0 (Current)
- ✅ Telegram 互動選單大改版：開始/暫停合併、統計總覽、門檻設定 (+/-)、重置數據
- ✅ Web 控制台可開關 + 自訂連接埠
- ✅ 密碼登入頁面 + IP 封鎖機制
- ✅ 達標通知只保留最新一個互動對話框
- ✅ 智慧平台判斷：自動偵測模擬器進程與 ADB 路徑

### v1.0.0
- ✅ MVC 架構重構
- ✅ Web 控制台與 Telegram 通知
- ✅ `mss` + `ppadb` 效能優化
- ✅ `Run.py` 智慧啟動器

---

> **Note**: This project is for educational and testing purposes only.