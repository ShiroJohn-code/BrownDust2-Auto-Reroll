# 🎮 無限抽自動化程式 (Infinite Gacha Automation)

基於 Python 開發的高效能自動抽卡輔助工具，採用 **MVC 架構**，整合 **FastAPI Web 控制台**、**Telegram 遠端互動控制** 以及 **ADB 極速通訊**。

支援三種操作模式：**純本機熱鍵**、**Web 網頁控制台**、**Telegram Bot 遠端操控**，可自由組合。

---

## ✨ 主要功能

### 🖥️ 雙平台自動化
- **Windows 桌面模式** — 視窗追蹤截圖 + 等比座標換算，自動跟隨遊戲視窗位置與大小
- **模擬器模式 (LDPlayer)** — `pure-python-adb` Socket 直連，自動偵測模擬器進程與 ADB 路徑

### 📱 Telegram Bot 遠端控制
- **一鍵開始/暫停** — 自動判斷狀態的切換按鈕
- **📊 統計總覽** — 運行狀態、抽卡統計、五星分布一頁看完
- **⚙️ 門檻設定** — 直接用 ➕➖ 按鈕即時調整 5星/4星門檻
- **🗑️ 重置數據** — 一鍵清除所有抽卡紀錄，從零開始
- **達標通知** — 自動截圖 + 互動式繼續/停止按鈕，永遠只保留最新一個對話框
- **Web UI 快捷連結** — 自動判斷 WebUI 是否啟用，動態顯示內網/外網按鈕

### 🌐 Web 控制台
- 即時監控畫面（快照模式）
- 動態調整抽卡門檻
- Telegram Bot 設定更新
- 密碼保護登入 + IP 封鎖機制（3 次錯誤鎖定 1 小時）
- 可透過 `config.ini` 開關及自訂連接埠

### 🛡️ 穩定健壯
- **智慧啟動器 (`Run.py`)** — 自動安裝依賴、取得管理員權限、攔截崩潰錯誤
- **視窗追蹤** — 自動尋找遊戲視窗，支援任意解析度與多螢幕環境
- **Telegram 初始化保護** — 使用 `threading.Event` 確保 Bot 真正就緒後才繼續，消除 race condition
- **閒置自動停止** — 連續 30 次循環無新抽卡記錄自動暫停並發送 Telegram 警報
- **日誌管理** — 自動輪替（5MB/檔，保留 3 份），過濾網路庫雜訊

---

## 📂 專案架構

```text
無限抽_2K/
├── Run.py                    # 🚀 智慧啟動器 (入口點)
├── main.py                   # 🧠 核心主程式 (MVC 架構)
├── config.ini                # ⚙️ 設定檔 (不納入版控)
├── config.example.ini        # ⚙️ 設定檔範本
├── requirements.txt          # 📦 依賴套件清單
│
├── mod/                      # 🔧 功能模組
│   ├── image_processor.py    #    OpenCV 圖像處理、星級分析
│   ├── input_handler.py      #    滑鼠/觸控操作封裝
│   ├── window_tracker.py     #    視窗追蹤與等比座標換算
│   ├── ld_controller.py      #    ADB Socket 通訊層
│   ├── web_ui.py             #    FastAPI Web 控制台 + 認證
│   ├── telegram_bot.py       #    Telegram Bot 互動控制器
│   ├── character_detector.py #    角色特徵比對辨識
│   └── auto_updater.py       #    自動更新模組
│
├── templates/                # 🎨 Web 前端 (Bootstrap 5)
│   └── index.html
├── logs/                     # 📝 系統日誌 (自動生成)
└── mouse/                    # 🖼️ 辨識用圖片資源
    ├── windows/              #    Windows 桌面模式圖片
    └── emulator/             #    模擬器模式圖片
```

---

## 🚀 快速開始

### 環境需求

- **Windows 10/11**
- **Python 3.10+**

### 啟動

直接雙擊 **`Run.py`** 即可，程式會自動：
1. 偵測 Python 版本
2. 檢查並安裝缺少的套件
3. 請求系統管理員權限
4. 啟動自動化程式

### ⚙️ 設定檔 (`config.ini`)

複製 `config.example.ini` 為 `config.ini` 並填入以下設定：

```ini
[Telegram]
token =                  # Telegram Bot Token (留空 = 不啟用)
chat_id =                # Telegram Chat ID (留空 = 啟動偵測模式)

[Emulator]
adb_path =               # ADB 路徑 (留空 = 自動偵測，找不到則用 Windows 模式)

[Thresholds]
min_5star = 1            # 5星達標門檻
min_4star = 0            # 4星達標門檻

[System]
start_hotkey = f6        # 啟動/暫停熱鍵 (預設 F6)

[Game]
window_title = BrownDust II  # 遊戲視窗標題

[WebUI]
enabled = true           # Web 控制台開關 (true/false)
port = 8964              # Web 控制台連接埠
password = admin         # Web 控制台登入密碼
```

> **Telegram chat_id 取得方式：** 填入 token 但留空 chat_id，啟動程式後對 Bot 傳送任意訊息，程式會自動顯示你的 chat_id。

### 操作模式

| 設定 | 行為 |
|------|------|
| Telegram ✅ WebUI ✅ | 完整功能：遠端 Bot + 網頁控制台 + 熱鍵 |
| Telegram ✅ WebUI ❌ | 純 Bot 遠端控制 + 熱鍵 |
| Telegram ❌ WebUI ✅ | 網頁控制台 + 熱鍵 |
| Telegram ❌ WebUI ❌ | 純本機熱鍵操作 |

### ⌨️ 熱鍵

| 按鍵 | 功能 |
|------|------|
| `F6` (可設定) | 啟動 / 暫停自動抽卡 |
| `F9` | 單次截圖分析 (Debug) |
| `F10` | 顯示五星分布統計 |
| `F12` | 顯示抽卡統計摘要 |

---

## 🛠️ 技術細節

1. **視窗追蹤截圖** — Windows 模式使用 `GetClientRect` + `ClientToScreen` 精確定位視窗，支援任意螢幕位置與解析度，座標自動等比換算
2. **ADB 通訊** — 透過 `pure-python-adb` Socket 長連線（Port 5037）取代 `subprocess` 指令，毫秒級響應
3. **Web 認證** — 純 ASGI 中間件 + Cookie Session + IP 封鎖，不依賴 `BaseHTTPMiddleware` 避免 Request Body 消耗問題
4. **Telegram 初始化** — 使用 `threading.Event` + `post_init` callback，確保 `ExtBot.initialize()` 完成後才進行任何 API 呼叫
5. **Telegram 訊息管理** — 追蹤 `last_notification_message_id`，新通知前自動刪除舊對話框，先發圖再發按鈕確保互動框在最底部

---

## 📅 版本紀錄

### v2.1.0 (Current)
- ✅ 移除指定螢幕功能，改由視窗追蹤完整覆蓋（支援多螢幕環境）
- ✅ Telegram Bot 初始化改用 `threading.Event`，修復 race condition 與 `ExtBot not initialized` 錯誤
- ✅ 補齊 Run.py 相依套件預檢清單（pyautogui、keyboard、requests、ppadb）

### v2.0.0
- ✅ Telegram 互動選單大改版：開始/暫停合併、統計總覽、門檻設定 (+/-)、重置數據
- ✅ Web 控制台可開關 + 自訂連接埠
- ✅ 密碼登入頁面 + IP 封鎖機制
- ✅ 達標通知只保留最新一個互動對話框
- ✅ 智慧平台判斷：自動偵測模擬器進程與 ADB 路徑
- ✅ 視窗追蹤：動態換算座標，支援任意視窗大小

### v1.0.0
- ✅ MVC 架構重構
- ✅ Web 控制台與 Telegram 通知
- ✅ `mss` + `ppadb` 效能優化
- ✅ `Run.py` 智慧啟動器

---

> **Note**: This project is for educational and testing purposes only.
