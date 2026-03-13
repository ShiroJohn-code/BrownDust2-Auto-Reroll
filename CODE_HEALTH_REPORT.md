# 程式碼全面健檢報告

## 檢查範圍
本次為靜態健檢，主要檢視 `main.py`、`mod/`、`Test/`、`config.ini`、`requirements.txt`、`README.md` 與近期 Git 紀錄。未實機執行 Telegram、ADB、Web UI，因此以下以可從程式碼直接驗證的問題為主。

## 總結
- 高風險問題 4 項：包含憑證外洩、Telegram 重載流程錯誤、截圖失敗仍持續點擊、Web 驗證信任可偽造標頭。
- 中風險問題 4 項：包含統計失真、檔案寫入競態、文件與實作脫節、錯誤處理不完整。
- 低風險/技術債 3 項：包含未使用模組、重複測試副本、依賴清單不完整。

## 重大問題

### 1. 已提交真實憑證與密碼
- 位置：`config.ini:2-3`, `config.ini:19`
- 問題：Telegram `token`、`chat_id` 與 Web UI `password` 直接存在版本庫。
- 風險：任何可讀取 repo 的人都能接管 Bot 或登入控制台。
- 建議：立刻撤換 Telegram Token、修改 Web 密碼、將 `config.ini` 改為範本檔（例如 `config.example.ini`），並將實際設定加入 `.gitignore`。

### 2. Telegram 重載流程沒有停止舊 Bot
- 位置：`main.py:369-375`, `mod/telegram_bot.py:35-73`, `mod/telegram_bot.py:83-97`
- 問題：`reload_telegram_bot()` 只把 `self.telegram_bot = None`，沒有呼叫 `stop_bot_sync()` 或等待舊 polling thread 結束。
- 影響：容易殘留舊執行緒，造成 Telegram `Conflict`、重複 polling、資源外洩。
- 建議：重載前先停止舊 `Application`，等待 thread 結束，再建立新實例。

### 3. 截圖失敗時主流程仍會盲點擊
- 位置：`main.py:491-516`
- 問題：`take_screenshot()` 若失敗回傳 `None`，`find_image()` 只會回 `False`，主流程最後進入 `else` 並點擊 `position_c`。
- 影響：ADB 斷線、螢幕抓取失敗或權限異常時，程式仍會持續操作畫面，容易誤點。
- 建議：若截圖為 `None`，應直接記錄錯誤並 `continue`，必要時自動暫停程式。

### 4. Web 驗證直接信任 `X-Forwarded-For`
- 位置：`mod/web_ui.py:93-99`
- 問題：只要 request 帶 `X-Forwarded-For` 就覆蓋真實來源 IP，沒有驗證是否真的來自受信任反向代理。
- 風險：攻擊者可偽造 IP 來繞過封鎖、污染失敗次數、誤封其他位址。
- 建議：只有在明確部署於受信任 proxy 後才讀取該標頭，否則應使用 `request.client.host`。

## 中度問題

### 5. 統計名稱與實際計算口徑不一致
- 位置：`main.py:73`, `main.py:269-283`, `main.py:294`
- 問題：`draw_records` 只保留最近 1000 筆，但 `show_draw_summary()` 顯示「總次數」與「成功率」，會讓人誤以為平均值與成功率是全量資料。
- 影響：抽卡次數高於 1000 後，儀表板與摘要會失真。
- 建議：要嘛保存全量聚合統計，要嘛 UI 明確標示「近 1000 筆」。

### 6. Telegram 重置資料未使用檔案鎖
- 位置：`mod/telegram_bot.py:155-163`, `main.py:255-266`
- 問題：`record_draw()` 寫入 `draw_records.txt` 有 `file_lock`，但 Telegram 的 `reset_data` 直接覆寫檔案沒有鎖。
- 影響：若重置與寫入同時發生，可能造成紀錄損毀或內容交錯。
- 建議：重用 `GameModel.reset_statistics()`，不要在 Bot 內自行操作檔案。

### 7. README 與主程式功能脫節
- 位置：`README.md:85-88`, `main.py:120-123`, `Test/main.py:139-141`
- 問題：README 仍宣稱支援 `min_score`，測試版 `Test/main.py` 也保留分數判斷；正式版 `main.py` 已完全不讀取/使用 `min_score`。
- 影響：使用者會以為分數門檻仍有效，形成設定誤導。
- 建議：若功能已移除，更新 README 與測試副本；若要保留，應在正式版補回一致實作。

### 8. `load_config()` 的外層錯誤處理不足
- 位置：`main.py:125-143`
- 問題：若讀檔過程發生較嚴重例外，外層只記錄 log，沒有保證 `min_5star`、`min_4star`、`monitor_index` 一定被初始化。
- 影響：後續流程可能在其他位置才因屬性不存在而失敗，增加除錯成本。
- 建議：在進入 `try` 前先設定預設值，或在外層 `except` 補齊 fallback。

## 低度問題 / 技術債

### 9. 測試依賴未寫入 `requirements.txt`
- 位置：`Test/test_ocr.py:1`, `requirements.txt:1-13`
- 問題：`Test/test_ocr.py` 直接依賴 `paddleocr`，但依賴清單沒有。
- 影響：依 README/requirements 安裝後，測試無法直接執行。
- 建議：將其加入開發依賴，或在測試檔案與文件明確標示額外安裝步驟。

### 10. 存在未使用或已分叉的舊代碼
- 位置：`mod/character_detector.py:1-20`, `Test/main.py:19-23`, `Test/main.py:139-141`
- 問題：正式版未引用 `CharacterDetector`，但 `Test/main.py` 仍保留一整套含分數判定的舊流程，`Test/mod/web_ui.py` 也是歷史副本。
- 影響：後續維護容易雙軌漂移，修一份漏一份。
- 建議：刪除確定不用的副本，或明確標記 `Test/` 內哪些是備份、哪些是可執行測試。

### 11. `SendInput` 成功與否未檢查
- 位置：`mod/input_handler.py:67-68`
- 問題：`SendInput()` 回傳值未驗證，函式直接 `return True`。
- 影響：在輸入被阻擋或 API 呼叫失敗時，主流程會誤判為點擊成功。
- 建議：檢查回傳事件數是否為 3，否則 fallback 到其他輸入方式。

## 冗餘代碼
- `mod/web_ui.py:71` 的 `update_ban_state()` 已無呼叫點，可刪除或整合到登入失敗流程。
- `Test/main.py` 與 `Test/mod/web_ui.py` 看起來更像歷史快照，不是最小化測試，建議從測試資料夾拆出或加上明確用途說明。

## 優化建議
- 將設定檔讀寫集中成單一設定服務或 dataclass，避免 `main.py`、`web_ui.py`、`telegram_bot.py` 分散寫檔。
- 為 `GameModel` 建立真正的聚合統計欄位，避免每次從 `deque` 重算與口徑混亂。
- 為 ADB、截圖與 Telegram 加入介面層，方便做 mock 測試。
- 增加最基本的 smoke tests：設定檔載入、統計計算、Web 認證、Telegram reload。
- 把 `print()` 統一改為 `logging`，否則多執行緒下很難追蹤事件順序。

## 建議修復順序
1. 先處理憑證撤換與設定檔分離。
2. 修正 Telegram reload 與 reset 競態。
3. 修正截圖失敗時的保護邏輯。
4. 修正 Web IP 判定與登入安全性。
5. 清理文件/測試副本與依賴清單。
