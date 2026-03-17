import os
import time
import threading
import traceback
import configparser
import logging
import ctypes
import subprocess  # 用於檢查系統進程
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections import deque

# 圖像與自動化庫
import cv2
import numpy as np
import pyautogui
import keyboard
import mss
from PIL import Image

# 自定義模組
from mod.telegram_bot import TelegramController
from mod.ld_controller import LDController
from mod.web_ui import WebController
from mod.image_processor import ImageProcessor
from mod.input_handler import InputHandler
from mod.window_tracker import WindowTracker

# 配置 PyAutoGUI 設定
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1

class GameModel:
    def __init__(self):
        # DPI Awareness — 必須在所有 Win32 呼叫之前設定
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except Exception:
            pass  # Windows 8 以下不支援，靜默失敗

        self.script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.image_dir = self.script_dir / 'mouse'
        
        # 路徑設定
        self.image_dir_win = self.image_dir / 'windows'
        self.image_dir_emu = self.image_dir / 'emulator'
        self.image1_path_win = str(self.image_dir_win / '1.png')
        self.image2_path_win = str(self.image_dir_win / '2.png')
        self.image1_path_emu = str(self.image_dir_emu / '1.png')
        self.image2_path_emu = str(self.image_dir_emu / '2.png')
        self.base_image1_path = str(self.image_dir / '1.png')
        self.base_image2_path = str(self.image_dir / '2.png')
        
        # 螢幕參數
        self.base_width = 1920
        self.base_height = 1080
        self.screen_width, self.screen_height = pyautogui.size()
        self.scale_x = self.screen_width / self.base_width
        self.scale_y = self.screen_height / self.base_height

        # 座標定義
        self.position_a_win = (1460, 1000)
        self.position_b_win = (1000, 670)
        self.position_c_win = (1760, 55)
        self.position_a_emu = (1350, 990)
        self.position_b_emu = (1050, 700)
        self.position_c_emu = (1735, 75)
        
        self.running = False
        self.stop_event = threading.Event()
        self.frame_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.latest_frame = None
        
        self.setup_logging()
        self.load_config()

        self.image1 = None
        self.image2 = None
        self.draw_count = 0
        self.draw_records = deque(maxlen=1000)
        self.log_file = self.script_dir / 'draw_records.txt'
        
        # 啟動時自動清理舊截圖
        self.cleanup_screenshots()
        
        self.platform = "windows"
        self.adb_path = ""
        self.adb_serial = None
        self.ld = None
        self.window_tracker = None  # 由 setup_platform() 初始化
        
        # [核心模組初始化]
        self.image_processor = ImageProcessor(self.platform)

    def setup_logging(self):
        """配置日誌系統"""
        log_dir = self.script_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'game_service.log'
        
        handlers = [
            RotatingFileHandler(
                log_file, 
                maxBytes=5*1024*1024,
                backupCount=3,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=handlers,
            force=True
        )
        
        # 過濾雜訊
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.getLogger("multipart").setLevel(logging.WARNING)

    def load_config(self):
        self.config = configparser.ConfigParser()
        self.config_path = self.script_dir / 'config.ini'
        
        defaults = {
            'Thresholds': {'min_5star': '1', 'min_4star': '0'},
            'System': {'monitor_index': '1'}
        }

        try:
            if self.config_path.exists():
                self.config.read(str(self.config_path), encoding='utf-8')
                logging.info("已讀取設定檔: config.ini")
            else:
                logging.warning("找不到設定檔，將建立新檔")
                for section, options in defaults.items():
                    self.config[section] = options
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    self.config.write(f)

            try:
                self.min_5star = self.config.getint('Thresholds', 'min_5star')
                self.min_4star = self.config.getint('Thresholds', 'min_4star')
                self.monitor_index = self.config.getint('System', 'monitor_index')
                self.start_hotkey = self.config.get('System', 'start_hotkey', fallback='f6').lower()
                self.window_title  = self.config.get('Game', 'window_title', fallback='BrownDust II')
            except (ValueError, configparser.Error) as e:
                logging.error(f"設定檔異常 ({e})，使用預設值")
                self.min_5star = 1
                self.min_4star = 0
                self.monitor_index = 1
                self.start_hotkey = 'f6'
                self.window_title  = 'BrownDust II'
                self.set_thresholds(1, 0)
                self.set_system_config(1)

        except Exception as e:
            logging.error(f"讀取設定檔發生嚴重錯誤: {e}")
            self.min_5star = 1
            self.min_4star = 0
            self.monitor_index = 1
            self.start_hotkey = 'f6'
            self.window_title  = 'BrownDust II'

    def cleanup_screenshots(self):
        """清理舊截圖"""
        screenshot_dir = self.script_dir / 'screenshots'
        if not screenshot_dir.exists(): return
        try:
            files = sorted(screenshot_dir.glob('*.png'), key=os.path.getmtime)
            max_files = 20
            if len(files) > max_files:
                for f in files[:len(files) - max_files]:
                    try: os.remove(f)
                    except Exception: pass
        except Exception: pass

    def set_system_config(self, monitor_index):
        try:
            self.monitor_index = int(monitor_index)
            if not self.config.has_section('System'): self.config.add_section('System')
            self.config.set('System', 'monitor_index', str(self.monitor_index))
            with open(self.config_path, 'w', encoding='utf-8') as f: self.config.write(f)
            logging.info(f"螢幕設定已更新為: {self.monitor_index}")
            return True
        except Exception: return False

    def reset_statistics(self):
        self.draw_count = 0
        self.draw_records.clear()
        try:
            with self.file_lock: # 使用鎖
                with open(self.log_file, "w", encoding="utf-8") as f:
                    f.write(f"=== 重置紀錄 ===\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            logging.info("紀錄已重置")
            return True
        except Exception: return False

    @property
    def image1_path(self): return self.image1_path_emu if self.platform == "emulator" and os.path.exists(self.image1_path_emu) else (self.image1_path_win if os.path.exists(self.image1_path_win) else self.base_image1_path)
    @property
    def image2_path(self): return self.image2_path_emu if self.platform == "emulator" and os.path.exists(self.image2_path_emu) else (self.image2_path_win if os.path.exists(self.image2_path_win) else self.base_image2_path)
    @property
    def position_a(self):
        if self.platform == "emulator": return self.position_a_emu
        if self.window_tracker:
            pos = self.window_tracker.scale_position(*self.position_a_win)
            if pos: return pos
        return (int(self.position_a_win[0]*self.scale_x), int(self.position_a_win[1]*self.scale_y))

    @property
    def position_b(self):
        if self.platform == "emulator": return self.position_b_emu
        if self.window_tracker:
            pos = self.window_tracker.scale_position(*self.position_b_win)
            if pos: return pos
        return (int(self.position_b_win[0]*self.scale_x), int(self.position_b_win[1]*self.scale_y))

    @property
    def position_c(self):
        if self.platform == "emulator": return self.position_c_emu
        if self.window_tracker:
            pos = self.window_tracker.scale_position(*self.position_c_win)
            if pos: return pos
        return (int(self.position_c_win[0]*self.scale_x), int(self.position_c_win[1]*self.scale_y))

    def _init_log_file(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f: f.write("=== 抽卡紀錄 ===\n\n")
        else:
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    self.draw_count = f.read().count("[第")
            except Exception: pass

    def load_images(self):
        try:
            if not os.path.exists(self.image1_path) or not os.path.exists(self.image2_path):
                logging.error(f"圖片缺失: {self.image1_path}")
                return False
            img1 = Image.open(self.image1_path)
            self.image1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
            img2 = Image.open(self.image2_path)
            self.image2 = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)
            logging.info(f"圖片載入成功 ({self.platform})")
            return True
        except Exception as e:
            logging.error(f"載入圖片錯誤: {e}")
            return False

    def take_screenshot(self):
        img = None
        try:
            if self.platform == "emulator" and self.ld:
                img = self.ld.screencap()
            else:
                if self.window_tracker:
                    img = self.window_tracker.capture()
                if img is None:
                    # fallback: 全螢幕截圖
                    with mss.mss() as sct:
                        target_idx = self.monitor_index
                        if target_idx > len(sct.monitors) - 1: target_idx = 1
                        monitor = sct.monitors[target_idx]
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                        if self.screen_width != self.base_width:
                            img = cv2.resize(img, (self.base_width, self.base_height), interpolation=cv2.INTER_AREA)

            if img is not None:
                with self.frame_lock: self.latest_frame = img.copy()
            return img
        except Exception as e:
            logging.error(f"截圖失敗: {e}")
            return None

    def meets_threshold(self, stars_5, stars_4):
        return (stars_5 >= self.min_5star) and (stars_4 >= self.min_4star)

    def set_thresholds(self, min_5star, min_4star):
        self.min_5star = min_5star
        self.min_4star = min_4star
        self.config.set('Thresholds', 'min_5star', str(min_5star))
        self.config.set('Thresholds', 'min_4star', str(min_4star))
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        logging.info(f"已更新門檻: 5星>={min_5star}, 4星>={min_4star}")

    def record_draw(self, stars_5, stars_4, stars_3, success=False):
        self.draw_count += 1
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        record = {"timestamp": timestamp, "draw_number": self.draw_count, "5_star": stars_5, "4_star": stars_4, "3_star": stars_3, "success": success}
        self.draw_records.append(record)
        try:
            # 使用鎖保護檔案寫入
            with self.file_lock:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    status = "達到目標" if success else "未達標"
                    f.write(f"[第 {self.draw_count} 次抽卡] {timestamp} - 5星: {stars_5}, 4星: {stars_4}, 3星: {stars_3} - {status}\n")
        except Exception: pass
        return record

    def get_draw_statistics(self):
        if not self.draw_records: return {"total_draws": self.draw_count, "total_5star": 0, "total_4star": 0, "avg_5star": 0.0, "avg_4star": 0.0, "success_draws": 0, "success_rate": 0.0}
        sample_size = len(self.draw_records)
        total_5star = sum(r["5_star"] for r in self.draw_records)
        total_4star = sum(r["4_star"] for r in self.draw_records)
        success_draws = sum(1 for r in self.draw_records if r["success"])
        return {
            "total_draws": self.draw_count,
            "total_5star": total_5star,
            "total_4star": total_4star,
            "avg_5star": total_5star / sample_size,
            "avg_4star": total_4star / sample_size,
            "success_draws": success_draws,
            "success_rate": (success_draws / sample_size) * 100
        }
    
    def get_five_star_distribution(self):
        dist = {}
        for r in self.draw_records:
            s5 = r.get('5_star', 0)
            dist[s5] = dist.get(s5, 0) + 1
        return dist

    def show_draw_summary(self):
        stats = self.get_draw_statistics()
        return f"\n=== 抽卡統計 ===\n總次數: {stats['total_draws']}\n平均5星: {stats['avg_5star']:.2f}\n成功率: {stats['success_rate']:.2f}%"
    
    def show_five_star_distribution(self):
        dist = self.get_five_star_distribution()
        summary = "\n=== 5星分布 ===\n"
        for s, c in sorted(dist.items()): summary += f"5星 x{s}: {c}次\n"
        return summary
    
class GameController:
    def __init__(self, model):
        self.model = model
        self.view = GameView()
        self.telegram_token = self.model.config.get('Telegram', 'token', fallback="")
        self.telegram_chat_id = self.model.config.get('Telegram', 'chat_id', fallback="")
        self.telegram_bot = None
        self.web_ui = None
        self.input_handler = InputHandler(self.model)
        self.test_mouse_functionality()
    
    def test_mouse_functionality(self):
        try: pyautogui.position()
        except Exception as e: self.view.show_error(f"滑鼠功能異常: {e}")
    
    def start(self):
        self.view.show_message("程式初始化中...")
        self.setup_platform()  # <--- 這裡會呼叫新的判斷邏輯
        
        if not self.model.load_images():
            self.view.show_error("載入圖片失敗")
            return
        
        self.model._init_log_file()
        self.register_hotkeys()
        self.init_telegram_bot()

        webui_enabled = self.model.config.get('WebUI', 'enabled', fallback='true').lower() == 'true'
        if webui_enabled:
            try:
                self.web_ui = WebController(self.model, self)
                self.web_ui.start()
            except Exception as e: logging.error(f"Web UI 啟動失敗: {e}")
        else:
            self.web_ui = None
            logging.info("Web UI 已停用 (config.ini [WebUI] enabled = false)")

        if self.telegram_bot:
            self.telegram_bot.send_startup_menu_sync()

        self.view.show_message(
            f"程式已就緒! 按 {self.model.start_hotkey.upper()} 開始/暫停, F12 顯示抽卡統計"
        )
        logging.info(f"當前門檻: 5星>={self.model.min_5star}, 4星>={self.model.min_4star}")
        
        threading.Thread(target=self.auto_click_process, daemon=True).start()
        
        try:
            while not self.model.stop_event.is_set(): time.sleep(0.5)
        except KeyboardInterrupt:
            self.view.show_message("正在停止程式...")
            self.model.stop_event.set()
        finally:
            if self.telegram_bot: self.view.show_message("正在關閉 Telegram Bot...")
            self.view.show_message("程式已結束")

    def init_telegram_bot(self):
        if not self.telegram_token:
            logging.info("未偵測到 Telegram 設定，使用本機模式")
            self.telegram_bot = None
            return

        if not self.telegram_chat_id:
            logging.info("Telegram token 已設定，但 chat_id 為空，啟動偵測模式")
            threading.Thread(target=self._detect_chat_id, daemon=True).start()
            self.telegram_bot = None
            return

        try:
            self.telegram_bot = TelegramController(self.telegram_token, self.telegram_chat_id, self.model, self)
            self.telegram_bot.start_bot_thread()
            logging.info("Telegram Bot 服務已啟動")
        except Exception as e:
            logging.error(f"Telegram Bot 啟動失敗: {e}")
            self.telegram_bot = None

    def _detect_chat_id(self):
        """token 有填但 chat_id 空白時，等待使用者傳訊息並顯示其 chat_id"""
        try:
            import requests
            TIMEOUT_SEC = 300  # 5 分鐘後放棄
            POLL_INTERVAL = 3

            logging.info("=" * 55)
            logging.info("【Telegram 設定引導】")
            logging.info(f"請開啟 Telegram，對你的 Bot 傳送任意訊息")
            logging.info(f"程式將自動顯示你的 chat_id（等待 {TIMEOUT_SEC//60} 分鐘）")
            logging.info("=" * 55)

            base_url = f"https://api.telegram.org/bot{self.telegram_token}"

            # 先清掉所有舊的 updates，避免顯示到歷史訊息的 chat_id
            resp = requests.get(f"{base_url}/getUpdates", params={"offset": -1}, timeout=10)
            data = resp.json()
            if data.get("ok") and data["result"]:
                offset = data["result"][-1]["update_id"] + 1
            else:
                offset = 0

            deadline = time.time() + TIMEOUT_SEC
            while time.time() < deadline:
                try:
                    resp = requests.get(
                        f"{base_url}/getUpdates",
                        params={"offset": offset, "timeout": POLL_INTERVAL},
                        timeout=POLL_INTERVAL + 5
                    )
                    data = resp.json()
                    if not data.get("ok"):
                        logging.warning(f"Telegram API 回傳錯誤: {data.get('description', '未知')}")
                        time.sleep(5)
                        continue

                    for update in data["result"]:
                        offset = update["update_id"] + 1
                        msg = update.get("message") or update.get("edited_message")
                        if msg and "chat" in msg:
                            detected_id = msg["chat"]["id"]
                            sender = msg["from"].get("username") or msg["from"].get("first_name", "未知")
                            logging.info("=" * 55)
                            logging.info(f"【偵測成功】來自 @{sender}")
                            logging.info(f"  你的 chat_id 是：{detected_id}")
                            logging.info(f"  請將以下內容填入 config.ini：")
                            logging.info(f"  [Telegram]")
                            logging.info(f"  chat_id = {detected_id}")
                            logging.info(f"  填入後重啟程式即可啟用 Telegram 功能")
                            logging.info("=" * 55)
                            return

                except requests.RequestException as e:
                    logging.warning(f"chat_id 偵測輪詢失敗: {e}")
                    time.sleep(5)

            logging.warning("chat_id 偵測逾時（5 分鐘），已停止偵測。如需啟用 Telegram，請手動填入 chat_id")

        except Exception as e:
            logging.error(f"chat_id 偵測發生錯誤: {e}")

    def reload_telegram_bot(self):
        logging.info("正在重啟 Telegram Bot...")
        if self.telegram_bot:
            self.telegram_bot.stop_bot_sync()
            time.sleep(1)
        self.telegram_bot = None 
        self.telegram_token = self.model.config.get('Telegram', 'token', fallback="")
        self.telegram_chat_id = self.model.config.get('Telegram', 'chat_id', fallback="")
        self.init_telegram_bot()
        return True

    # [新增] 檢查模擬器進程是否在執行
    def check_emulator_process(self):
        """檢查系統中是否有常見模擬器進程"""
        emulator_processes = [
            "dnplayer.exe",   # 雷電模擬器 (LDPlayer)
            "HD-Player.exe",  # BlueStacks
            "Nox.exe",        # 夜神模擬器
            "LdVBoxHeadless.exe" # 雷電背景進程
        ]
        
        try:
            # 使用 tasklist 指令獲取所有執行中的進程
            output = subprocess.check_output(["tasklist"], creationflags=0x08000000).decode('mbcs', errors='ignore')
            for proc in emulator_processes:
                if proc.lower() in output.lower():
                    logging.info(f"偵測到模擬器進程: {proc}")
                    return True
        except Exception as e:
            logging.warning(f"進程檢查失敗: {e}")
        return False

    # [新增] 自動尋找 ADB 路徑
    def auto_find_adb(self):
        """自動搜尋常見的 ADB 路徑"""
        common_paths = [
            r"C:\LDPlayer\LDPlayer9\adb.exe",
            r"C:\leidian\LDPlayer9\adb.exe",
            r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
            r"C:\Program Files\Nox\bin\adb.exe",
            r"D:\LDPlayer\LDPlayer9\adb.exe",
            r"D:\leidian\LDPlayer9\adb.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    # [修改] 智慧平台判斷邏輯
    def setup_platform(self):
        # 1. 先讀取 Config
        config_adb = self.model.config.get('Emulator', 'adb_path', fallback="")
        
        # 2. 如果 Config 沒填，嘗試自動尋找
        if not config_adb or not os.path.exists(config_adb):
            found_adb = self.auto_find_adb()
            if found_adb:
                logging.info(f"自動偵測到 ADB 路徑: {found_adb}")
                config_adb = found_adb
                # 自動寫回設定檔
                if not self.model.config.has_section('Emulator'):
                    self.model.config.add_section('Emulator')
                self.model.config.set('Emulator', 'adb_path', found_adb)
                with open(self.model.config_path, 'w', encoding='utf-8') as f:
                    self.model.config.write(f)

        # 3. 【關鍵修復】進程檢查：如果模擬器沒開，直接切換到 Windows 模式
        # 這樣就解決了 "關閉模擬器後仍判定為 Emulator" 的問題
        is_emu_running = self.check_emulator_process()
        
        if config_adb and os.path.exists(config_adb) and is_emu_running:
            logging.info(f"嘗試連接 ADB: {config_adb}")
            self.model.platform = "emulator"
            self.model.adb_path = config_adb
            try:
                temp_ld = LDController(adb_path=config_adb)
                devs = temp_ld.list_devices()
                if devs:
                    serial = list(devs.keys())[0]
                    self.model.adb_serial = serial
                    self.model.ld = LDController(adb_path=config_adb, serial=serial)
                    logging.info(f"已連接模擬器: {serial}")
                    self.model.image_processor.update_platform("emulator")
                    self.model.window_tracker = None  # 模擬器模式不使用視窗追蹤
                    return
            except Exception as e: logging.warning(f"模擬器連接失敗: {e}")

        # 4. 回退到 Windows 模式
        self.model.platform = "windows"
        self.model.image_processor.update_platform("windows")
        logging.info("使用平台: Windows (桌面模式)")
        self.model.window_tracker = WindowTracker(self.model.window_title)
        if not self.model.window_tracker.find():
            logging.warning(f"啟動時找不到視窗 '{self.model.window_title}'，將於按下熱鍵時重試")

    def register_hotkeys(self):
        try:
            keyboard.add_hotkey(self.model.start_hotkey, self.toggle_program)
        except Exception as e:
            logging.error(f"熱鍵 '{self.model.start_hotkey}' 設定失敗: {e}，改用 f6")
            keyboard.add_hotkey('f6', self.toggle_program)
        keyboard.add_hotkey('f12', lambda: self.view.show_message(self.model.show_draw_summary()))
        keyboard.add_hotkey('f10', lambda: self.view.show_message(self.model.show_five_star_distribution()))
        keyboard.add_hotkey('f9', self.detect_current_screen)
        
    def toggle_program(self):
        if self.model.platform == "windows":
            if self.model.window_tracker is None or not self.model.window_tracker.is_available():
                self.view.show_message(
                    f"無法啟動：找不到遊戲視窗 '{self.model.window_title}'，請確認遊戲正在執行中"
                )
                return
        self.model.running = not self.model.running
        if self.model.running and self.model.platform == "windows" and self.model.window_tracker:
            self.model.window_tracker.bring_to_front()
            time.sleep(0.2)
        status = "啟動" if self.model.running else "暫停"
        self.view.show_message(f"=== 自動抽卡已{status} ===")

    def detect_current_screen(self):
        try:
            self.view.show_message("執行 F9 單次檢測...")
            screenshot = self.model.take_screenshot()
            timestamp = time.strftime("%H%M%S")
            debug_path = f"screenshots/debug_{timestamp}"
            os.makedirs("screenshots", exist_ok=True)
            
            stars_5, stars_4, regions = self.model.image_processor.analyze_stars(screenshot, True, debug_path)
            
            passed = self.model.meets_threshold(stars_5, stars_4)
            self.view.show_message(f"檢測結果: 5星={stars_5}, 4星={stars_4}, 達標={passed}")
        except Exception: traceback.print_exc()

    def click_position(self, position):
        return self.input_handler.click(position)
    
    def auto_click_process(self):
        logging.info("自動點擊執行緒啟動")
        MAX_NO_DRAW_CYCLES = 30  # 連續幾次循環無新抽卡記錄則自動停止
        no_draw_cycles = 0
        last_draw_count = self.model.draw_count
        was_running = False

        while not self.model.stop_event.is_set():
            if self.model.running:
                # 從暫停切換到啟動時重置閒置計數器
                if not was_running:
                    last_draw_count = self.model.draw_count
                    no_draw_cycles = 0
                    was_running = True

                try:
                    # 偵測抽卡計數是否有增加
                    current_count = self.model.draw_count
                    if current_count > last_draw_count:
                        last_draw_count = current_count
                        no_draw_cycles = 0
                    else:
                        no_draw_cycles += 1

                    # 超過閾值時自動停止並發送警報
                    if no_draw_cycles >= MAX_NO_DRAW_CYCLES:
                        logging.warning(f"連續 {MAX_NO_DRAW_CYCLES} 次循環未記錄新抽卡，自動停止")
                        self.model.running = False
                        was_running = False
                        no_draw_cycles = 0
                        if self.telegram_bot:
                            alert_text = (
                                f"⚠️ **自動停止警告**\n\n"
                                f"抽獎啟動中但連續 **{MAX_NO_DRAW_CYCLES}** 次循環內無新抽卡記錄，已自動停止。\n\n"
                                f"📌 **可能原因：**\n"
                                f"• 遊戲畫面異常或卡住\n"
                                f"• 模擬器/遊戲崩潰\n"
                                f"• 圖片辨識失效\n\n"
                                f"📊 已記錄抽卡次數：{self.model.draw_count} 次\n\n"
                                "請檢查後手動重新啟動。"
                            )
                            self.telegram_bot.send_message_sync(alert_text, self.telegram_bot.get_main_keyboard())
                        continue

                    screenshot = self.model.take_screenshot()
                    if screenshot is None:
                        logging.warning("截圖失敗，跳過本次循環")
                        time.sleep(1)
                        continue

                    img1_ok = self.model.image_processor.find_image(self.model.image1, screenshot)
                    img2_ok = self.model.image_processor.find_image(self.model.image2, screenshot)

                    if img1_ok and img2_ok:
                        self.click_position(self.model.position_b)
                        time.sleep(0.5)
                    elif img1_ok:
                        s5, s4, regions = self.model.image_processor.analyze_stars(screenshot)
                        s3 = max(0, 10 - s5 - s4)
                        success = self.model.meets_threshold(s5, s4)
                        self.model.record_draw(s5, s4, s3, success)
                        if success:
                            logging.info(f"達標! 5星:{s5}, 4星:{s4}")
                            if self.telegram_bot: self.telegram_bot.send_success_notification_sync(screenshot, s5, s4, s3)
                            self.model.running = False
                            was_running = False
                            no_draw_cycles = 0
                            while not self.model.running and not self.model.stop_event.is_set(): time.sleep(0.5)
                            if self.model.running:
                                self.click_position(self.model.position_a)
                                time.sleep(1)
                        else:
                            self.click_position(self.model.position_a)
                            time.sleep(0.5)
                    else:
                        self.click_position(self.model.position_c)
                        time.sleep(1)
                    time.sleep(0.1)
                except Exception as e:
                    logging.error(f"執行錯誤: {e}")
                    time.sleep(1)
            else:
                was_running = False
                time.sleep(0.5)

class GameView:
    def show_message(self, message): logging.info(message)
    def show_error(self, error_message): logging.error(error_message)

if __name__ == "__main__":
    model = GameModel()
    controller = GameController(model)
    controller.start()