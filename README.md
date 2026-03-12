# 🎮 無限抽自動化程式 (Infinite Gacha Automation)

這是一個基於 Python 開發的高效能自動抽卡輔助工具。採用 **MVC 架構** 設計，整合了 **FastAPI Web 控制台**、**Telegram 遠端通知** 以及 **ADB 極速通訊** 技術。

---

## ✨ 主要功能 (Features)

* **雙模式支援**：
* 🖥️ **Windows 桌面模式**：使用 `mss` 進行毫秒級極速截圖，`ctypes` 底層驅動滑鼠。
* 📱 **模擬器模式 (LDPlayer)**：使用 `pure-python-adb` 透過 Socket 直接通訊，擺脫傳統 ADB 指令的延遲。


* **Web 控制台 (Dashboard)**：
* 即時監控畫面 (MJPEG Stream)。
* 動態調整抽卡門檻 (5星數量、分數)。
* 支援內網/外網連線資訊顯示。


* **智慧通知**：
* Telegram Bot 整合，達標自動截圖發送通知。
* 提供 Web UI 快速連線連結。


* **穩定健壯**：
* **智慧啟動器 (`Run.py`)**：自動修復依賴、獲取管理員權限、攔截崩潰錯誤。
* **日誌管理**：自動輪替 (Log Rotation) 與雜訊過濾，避免硬碟塞滿。
* **執行緒安全**：修正了 `mss` 與 `httpx` 在多執行緒下的衝突問題。



---

## 🏗️ 專案架構 (Architecture)

本專案嚴格遵循 **MVC (Model-View-Controller)** 設計模式，確保代碼低耦合、易維護。

### 📂 檔案結構導覽

```text
無限抽_2K/
├── Run.py                  # 🚀 智慧啟動器 (入口點，負責環境建置與錯誤攔截)
├── main.py                 # 🧠 核心主程式 (MVC 組裝與主迴圈)
├── config.ini              # ⚙️ 設定檔 (由程式自動生成與維護)
├── requirements.txt        # 📦 依賴套件清單
│
├── mod/                    # 🔧 功能模組庫
│   ├── image_processor.py  # [視覺] OpenCV 圖像處理、星星分析 (邏輯剝離)
│   ├── input_handler.py    # [輸入] 滑鼠/觸控操作封裝 (Windows API / ADB Tap)
│   ├── ld_controller.py    # [通訊] ADB Socket 通訊層 (取代 subprocess)
│   ├── web_ui.py           # [介面] FastAPI 伺服器與串流處理
│   ├── telegram_bot.py     # [通知] Telegram Bot 控制器
│   └── character_detector.py # [辨識] 角色特徵比對邏輯
│
├── templates/              # 🎨 Web 前端模板 (Bootstrap 5)
│   └── index.html
├── logs/                   # 📝 系統日誌 (自動輪替)
└── mouse/                  # 🖼️ 辨識用圖片資源

```

---

## 🚀 快速開始 (Getting Started)

### 1. 環境準備

本程式專為 **Windows 10/11** 設計，建議使用 **Python 3.10+**。

### 2. 啟動方式

無需手動輸入指令，直接執行 **`Run.py`** 即可：

1. 雙擊 `Run.py`。
2. 程式會自動檢查並安裝缺少的套件 (`pip install -r requirements.txt`)。
3. 自動請求「系統管理員權限」以控制滑鼠。
4. 啟動成功後，瀏覽器輸入控制台網址（如 `http://localhost:8964`）。

### 3. 操作熱鍵

* `F5`: **啟動 / 暫停** 自動掛機。
* `F9`: **單次測試截圖** (Debug 用，結果存於 `screenshots/`)。
* `F10`: 顯示 5 星分布統計。
* `F12`: 顯示抽卡統計摘要。

---

## 🛠️ 開發者指南 (For Developers)

### 關鍵實作細節

1. **截圖效能優化 (`mss`)**：
* 在 Windows 模式下，我們使用 `mss` 取代 `pyautogui`。
* ⚠️ **注意**：`mss` 在多執行緒環境下非執行緒安全。在 `main.py` 的 `take_screenshot` 中，我們採用 `with mss.mss() as sct:` 的方式，確保每次截圖都建立獨立實例，防止崩潰。


2. **ADB 通訊優化 (`mod/ld_controller.py`)**：
* 棄用了 `subprocess.run("adb shell ...")` 的慢速方法。
* 改用 `ppadb (pure-python-adb)` 建立 Socket 長連線 (Port 5037)，實現毫秒級截圖與點擊。


3. **日誌系統 (`setup_logging`)**：
* 使用了 `RotatingFileHandler`，單檔限制 2MB，保留 5 份。
* 強制過濾了 `httpx`, `httpcore` 等網路庫的 INFO 等級日誌，避免 Telegram 輪詢訊息洗版。


4. **Web 與主程互動**：
* Web UI 運行於獨立執行緒 (`uvicorn`)。
* 利用 `GameModel` 作為共享狀態，並透過 `frame_lock` 保護圖片讀寫，防止 Race Condition 導致的畫面撕裂或黑畫面。



---

## 📅 版本紀錄 (Changelog)

### v1.0.0 (Current)

* ✅ 完成 MVC 架構重構。
* ✅ 實作 Web 控制台與 Telegram 雙向通知。
* ✅ 導入 `mss` 與 `ppadb` 進行效能優化。
* ✅ 加入 `Run.py` 智慧啟動與錯誤攔截機制。

### v2.0.0 (Planned)

* 🔄 **OCR 升級**：導入 AI 文字辨識，移除對圖片模板的依賴。
* 📦 **封裝發布**：使用 PyInstaller 打包為單一執行檔 (.exe)。

---

> **Note**: This project is for educational and testing purposes only.