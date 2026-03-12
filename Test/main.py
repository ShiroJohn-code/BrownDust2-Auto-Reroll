import os
import time
import threading
import traceback
import configparser
import logging
from pathlib import Path
from collections import deque
import ctypes
from ctypes import wintypes

import cv2
import numpy as np
import pyautogui
import keyboard
from PIL import Image

# 自定義模組
from mod.telegram_bot import TelegramController
from mod.character_detector import CharacterDetector
from mod.ld_controller import LDController
from mod.web_ui import WebController

# 配置 PyAutoGUI 設定
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1

# Windows API 常數
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

# MVC架構實現
# Model: 處理數據和業務邏輯
class GameModel:
    def __init__(self):
        # 設定路徑
        self.script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.image_dir = self.script_dir / 'mouse'
        
        # 建立 mouse 資料夾結構 (如果不存在)
        self.image_dir_win = self.image_dir / 'windows'
        self.image_dir_emu = self.image_dir / 'emulator'
        
        # 圖片路徑定義
        self.image1_path_win = str(self.image_dir_win / '1.png')
        self.image2_path_win = str(self.image_dir_win / '2.png')
        self.image1_path_emu = str(self.image_dir_emu / '1.png')
        self.image2_path_emu = str(self.image_dir_emu / '2.png')
        # 相容舊版路徑
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
        
        # 運行狀態
        self.running = False
        self.stop_event = threading.Event()
        
        # [效能優化] 截圖快取機制
        self.frame_lock = threading.Lock() # 確保執行緒安全
        self.latest_frame = None           # 儲存最新畫面
        
        # 初始化系統
        self.setup_logging()
        self.load_config()

        # 載入圖片資源
        self.image1 = None
        self.image2 = None
        
        # 數據記錄
        self.draw_count = 0
        self.draw_records = deque(maxlen=1000)
        self.log_file = self.script_dir / 'draw_records.txt'
        
        # 功能模組
        self.click_method = "auto"
        self.character_detector = CharacterDetector(self.script_dir / 'get')
        
        # 平台設定
        self.platform = "windows"
        self.adb_path = ""
        self.adb_serial = None
        self.ld = None

        # 分析參數
        self.star_region_win = (370, 1545, 650, 675)
        self.star_region_emu = (255, 1660, 678, 700)
        self.density_thresholds_win = (25.0, 33.0)
        self.density_thresholds_emu = (30.0, 38.0)

    def setup_logging(self):
        """配置日誌系統 (純文字模式)"""
        log_dir = self.script_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d")
        log_file = log_dir / f'game_{timestamp}.log'
        
        # 同時輸出到檔案與控制台
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )
        logging.info("日誌系統已啟動 (Clean Mode)")

    def load_config(self):
        """讀取設定檔"""
        self.config = configparser.ConfigParser()
        self.config_path = self.script_dir / 'config.ini'
        
        if self.config_path.exists():
            self.config.read(str(self.config_path), encoding='utf-8')
            logging.info("已讀取設定檔: config.ini")
        else:
            logging.warning("找不到設定檔，使用預設值")

        # 讀取門檻
        self.min_5star = self.config.getint('Thresholds', 'min_5star', fallback=1)
        self.min_4star = self.config.getint('Thresholds', 'min_4star', fallback=0)
        self.min_score = self.config.getint('Thresholds', 'min_score', fallback=0)

    # --- 屬性存取器 (保持不變) ---
    def get_star_region(self):
        return self.star_region_emu if self.platform == "emulator" else self.star_region_win

    def get_density_thresholds(self):
        return self.density_thresholds_emu if self.platform == "emulator" else self.density_thresholds_win

    @property
    def image1_path(self):
        p = self.image1_path_emu if self.platform == "emulator" else self.image1_path_win
        return p if os.path.exists(p) else self.base_image1_path

    @property
    def image2_path(self):
        p = self.image2_path_emu if self.platform == "emulator" else self.image2_path_win
        return p if os.path.exists(p) else self.base_image2_path

    @property
    def position_a(self):
        pos = self.position_a_emu if self.platform == "emulator" else self.position_a_win
        return (int(pos[0] * self.scale_x), int(pos[1] * self.scale_y)) if self.platform == "windows" else pos

    @property
    def position_b(self):
        pos = self.position_b_emu if self.platform == "emulator" else self.position_b_win
        return (int(pos[0] * self.scale_x), int(pos[1] * self.scale_y)) if self.platform == "windows" else pos

    @property
    def position_c(self):
        pos = self.position_c_emu if self.platform == "emulator" else self.position_c_win
        return (int(pos[0] * self.scale_x), int(pos[1] * self.scale_y)) if self.platform == "windows" else pos
    
    # --- 核心邏輯方法 ---
    def _init_log_file(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write(f"{'='*80}\n無限抽自動化程式 - 抽卡紀錄\n開始時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*80}\n\n")
        else:
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    draw_count = content.count("[第")
                    if draw_count > 0:
                        self.draw_count = draw_count
                        logging.info(f"已讀取現有紀錄，總抽卡次數: {self.draw_count}")
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'-'*50}\n繼續抽卡時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            except Exception as e:
                logging.error(f"讀取紀錄檔案錯誤: {e}")

    def load_images(self):
        try:
            if not os.path.exists(self.image1_path) or not os.path.exists(self.image2_path):
                logging.error(f"圖片缺失: {self.image1_path} 或 {self.image2_path}")
                return False
                
            img1 = Image.open(self.image1_path)
            self.image1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
            
            img2 = Image.open(self.image2_path)
            self.image2 = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)
            
            logging.info(f"圖片載入成功 ({self.platform})")
            return True
        except Exception as e:
            logging.error(f"載入圖片時發生錯誤: {e}")
            return False
    
    def take_screenshot(self):
        """
        截取螢幕，並同時更新快取 (解決 Race Condition 核心)
        """
        img = None
        try:
            if self.platform == "emulator" and self.ld:
                img = self.ld.screencap()
            else:
                screenshot = pyautogui.screenshot()
                img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                
                if self.platform == "windows" and (self.screen_width != self.base_width):
                    img = cv2.resize(img, (self.base_width, self.base_height), interpolation=cv2.INTER_AREA)
            
            # [效能優化] 更新快取
            if img is not None:
                with self.frame_lock:
                    self.latest_frame = img.copy() # 存一份副本，避免其他執行緒修改影響
            
            return img
        except Exception as e:
            logging.error(f"截圖失敗: {e}")
            return None
    
    def find_image_on_screen(self, template, screenshot, threshold=0.8):
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        return len(locations[0]) > 0
    
    def analyze_stars(self, screenshot, debug_mode=False, debug_path=None):
        h, w = screenshot.shape[:2]
        x1, x2, y1, y2 = self.get_star_region()
        star_region = screenshot[y1:y2, x1:x2]
        
        if debug_mode and debug_path:
            cv2.imwrite(f"{debug_path}_star_region.png", star_region)
        
        hsv = cv2.cvtColor(star_region, cv2.COLOR_BGR2HSV)
        lower_yellow = np.array([15, 70, 150])
        upper_yellow = np.array([45, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        kernel = np.ones((3, 3), np.uint8)
        dilated_mask = cv2.dilate(yellow_mask, kernel, iterations=1)
        
        region_width = x2 - x1
        gap_width = 25
        total_gaps = 9 * gap_width
        effective_width = region_width - total_gaps
        segment_width = effective_width // 10
        
        star_counts = []
        five_star_regions = []
        
        for i in range(10):
            left = i * (segment_width + gap_width)
            right = left + segment_width
            segment_mask = dilated_mask[:, left:right]
            
            yellow_pixel_count = np.sum(segment_mask > 0)
            total_pixels = segment_mask.shape[0] * segment_mask.shape[1]
            density = (yellow_pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            
            t34, t45 = self.get_density_thresholds()
            
            if density < t34:
                star_count = 3
            elif density < t45:
                star_count = 4
            else:
                star_count = 5
            
            if star_count == 5:
                char_x1 = max(0, x1 + left - 30)
                char_x2 = min(w, x1 + right + 30)
                char_y1 = max(0, y2 - 450)
                char_y2 = y2
                five_star_regions.append((char_x1, char_y1, char_x2, char_y2))
                
            star_counts.append(star_count)
        
        return star_counts.count(5), star_counts.count(4), five_star_regions
    
    def detect_five_star_characters(self, screenshot, five_star_regions, debug_mode=False, debug_path=None):
        if not five_star_regions:
            return [], 0, ""
        
        detected = self.character_detector.detect_characters_in_regions(
            screenshot, five_star_regions, debug_mode, debug_path
        )
        score = self.character_detector.calculate_total_score(detected)
        info = self.character_detector.format_characters_info(detected)
        
        if debug_mode:
            logging.info(f"檢測到的5星角色: {info}")
        return detected, score, info
    
    def meets_threshold(self, stars_5, stars_4, total_score=0):
        return (stars_5 >= self.min_5star) and (stars_4 >= self.min_4star) and (total_score >= self.min_score)
    
    def set_thresholds(self, min_5star, min_4star, min_score=0):
        self.min_5star = min_5star
        self.min_4star = min_4star
        self.min_score = min_score
        
        # 同步更新 config 物件 (暫不寫入檔案，等待 WebUI 實作)
        self.config.set('Thresholds', 'min_5star', str(min_5star))
        self.config.set('Thresholds', 'min_4star', str(min_4star))
        self.config.set('Thresholds', 'min_score', str(min_score))
        
        logging.info(f"已更新門檻: 5星>={min_5star}, 4星>={min_4star}, 分數>={min_score}")
        
    def record_draw(self, stars_5, stars_4, stars_3, success=False):
        self.draw_count += 1
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        record = {
            "timestamp": timestamp,
            "draw_number": self.draw_count,
            "5_star": stars_5,
            "4_star": stars_4,
            "3_star": stars_3,
            "success": success
        }
        self.draw_records.append(record)
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                status = "達到目標" if success else "未達標"
                f.write(f"[第 {self.draw_count} 次抽卡] {timestamp} - 5星: {stars_5}, 4星: {stars_4}, 3星: {stars_3} - {status}\n")
        except Exception:
            pass
            
        return record
    
    def get_draw_statistics(self):
        if not self.draw_records:
            return {"total_draws": self.draw_count, "avg_5star": 0.0, "avg_4star": 0.0, "success_rate": 0.0}
        
        sample_size = len(self.draw_records)
        total_5star = sum(r["5_star"] for r in self.draw_records)
        total_4star = sum(r["4_star"] for r in self.draw_records)
        success_draws = sum(1 for r in self.draw_records if r["success"])
        
        return {
            "total_draws": self.draw_count,
            "avg_5star": total_5star / sample_size,
            "avg_4star": total_4star / sample_size,
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
        summary = f"\n=== 抽卡統計 (近{len(self.draw_records)}筆) ===\n"
        summary += f"總次數: {stats['total_draws']}\n"
        summary += f"平均5星: {stats['avg_5star']:.2f}\n"
        summary += f"平均4星: {stats['avg_4star']:.2f}\n"
        summary += f"成功率: {stats['success_rate']:.2f}%\n"
        return summary
    
    def show_five_star_distribution(self):
        dist = self.get_five_star_distribution()
        summary = "\n=== 5星分布 ===\n"
        for s, c in sorted(dist.items()):
            summary += f"5星 x{s}: {c}次\n"
        return summary

# Controller: 控制程式流程
class GameController:
    def __init__(self, model):
        self.model = model
        self.view = GameView()
        
        # [安全性修正] 讀取設定檔，若無則為空
        self.telegram_token = self.model.config.get('Telegram', 'token', fallback="")
        self.telegram_chat_id = self.model.config.get('Telegram', 'chat_id', fallback="")
        self.telegram_bot = None
        self.web_ui = None
        
        self.test_mouse_functionality()
    
    def test_mouse_functionality(self):
        try:
            pyautogui.position()
        except Exception as e:
            self.view.show_error(f"滑鼠功能異常: {e} (請使用系統管理員執行)")
    
    def start(self):
        self.view.show_message("程式初始化中...")
        self.setup_platform()
        
        if self.model.platform == "windows":
            # Windows 點擊設定可在此擴充
            pass
        
        if not self.model.load_images():
            self.view.show_error("載入圖片失敗，程式無法繼續")
            return
        
        self.model._init_log_file()
        self.register_hotkeys()
        self.init_telegram_bot()

        # [Web UI 啟動邏輯]
        try:
            self.web_ui = WebController(self.model, self)
            self.web_ui.start()
            # logging.info 已在 web_ui 內部處理
        except Exception as e:
            logging.error(f"Web UI 啟動失敗: {e}")

        self.view.show_message("程式已就緒! 按 F5 開始/暫停, F9 測試截圖")
        logging.info(f"當前門檻: 5星>={self.model.min_5star}, 4星>={self.model.min_4star}, 分數>={self.model.min_score}")
        
        # 啟動自動點擊執行緒
        threading.Thread(target=self.auto_click_process, daemon=True).start()
        
        # 主迴圈 (保持程式運行)
        try:
            while not self.model.stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.view.show_message("正在停止程式...")
            self.model.stop_event.set()
        finally:
            if self.telegram_bot:
                self.view.show_message("正在關閉 Telegram Bot...")
                self.telegram_bot.stop_bot_sync()
            self.view.show_message("程式已結束")
    
    def init_telegram_bot(self):
        # [邏輯修正] 檢查是否有有效的 Token
        if not self.telegram_token or not self.telegram_chat_id:
            logging.warning("未設定 Telegram Token，遠端功能已停用")
            return

        try:
            self.telegram_bot = TelegramController(
                self.telegram_token, self.telegram_chat_id, self.model, self
            )
            self.telegram_bot.start_bot_thread()
            logging.info("Telegram Bot 服務已啟動")
        except Exception as e:
            logging.error(f"Telegram Bot 啟動失敗: {e}")
            self.telegram_bot = None
            
    def setup_platform(self):
        # 優先使用設定檔
        config_adb = self.model.config.get('Emulator', 'adb_path', fallback="")
        if config_adb and os.path.exists(config_adb):
            logging.info(f"使用設定檔 ADB: {config_adb}")
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
                    return
            except Exception as e:
                logging.warning(f"模擬器連接失敗: {e}，切換回 Windows")
        
        # 如果設定檔沒寫，預設 Windows
        self.model.platform = "windows"
        logging.info("使用平台: Windows (桌面模式)")

    def register_hotkeys(self):
        keyboard.add_hotkey('f5', self.toggle_program)
        keyboard.add_hotkey('f12', self.show_statistics)
        keyboard.add_hotkey('f10', lambda: self.view.show_message(self.model.show_five_star_distribution()))
        keyboard.add_hotkey('f9', self.detect_current_screen)
        
    def toggle_program(self):
        self.model.running = not self.model.running
        status = "啟動" if self.model.running else "暫停"
        self.view.show_message(f"=== 自動抽卡已{status} ===")
        
    def show_statistics(self):
        self.view.show_message(self.model.show_draw_summary())
    
    def detect_current_screen(self):
        try:
            self.view.show_message("執行 F9 單次檢測...")
            screenshot = self.model.take_screenshot()
            
            timestamp = time.strftime("%H%M%S")
            debug_path = f"screenshots/debug_{timestamp}"
            os.makedirs("screenshots", exist_ok=True)
            
            stars_5, stars_4, regions = self.model.analyze_stars(screenshot, True, debug_path)
            
            info = "無"
            score = 0
            if stars_5 > 0:
                _, score, info = self.model.detect_five_star_characters(screenshot, regions, True, debug_path)
            
            passed = self.model.meets_threshold(stars_5, stars_4, score)
            self.view.show_message(f"檢測結果: 5星={stars_5}, 4星={stars_4}, 總分={score}, 達標={passed}")
            self.view.show_message(f"角色資訊: {info}")
            
        except Exception:
            logging.error("檢測時發生錯誤")
            traceback.print_exc()

    # --- 點擊與自動化邏輯 ---
    def click_position(self, position):
        x, y = position
        try:
            if self.model.platform == "emulator" and self.model.ld:
                return self.model.ld.tap(x, y)
            
            # Windows 優先 SendInput
            if self.send_input_click(x, y): return True
            # 備用 WinAPI
            if self.windows_api_click(x, y): return True
            # 最後 PyAutoGUI
            pyautogui.click(x, y)
            return True
        except: return False
            
    def windows_api_click(self, x, y):
        try:
            ctypes.windll.user32.SetCursorPos(x, y)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            return True
        except: return False
    
    def send_input_click(self, x, y):
        try:
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            abs_x = int(x * 65535 / screen_w)
            abs_y = int(y * 65535 / screen_h)
            
            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD),
                           ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
            class INPUT(ctypes.Structure):
                class _INPUT(ctypes.Union): _fields_ = [("mi", MOUSEINPUT)]
                _anonymous_ = ("_input",); _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]
            
            mi_move = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE|MOUSEEVENTF_ABSOLUTE, 0, None)
            mi_down = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTDOWN|MOUSEEVENTF_ABSOLUTE, 0, None)
            mi_up = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTUP|MOUSEEVENTF_ABSOLUTE, 0, None)
            
            inputs = (INPUT * 3)()
            inputs[0].type = 0; inputs[0].mi = mi_move
            inputs[1].type = 0; inputs[1].mi = mi_down
            inputs[2].type = 0; inputs[2].mi = mi_up
            
            ctypes.windll.user32.SendInput(3, inputs, ctypes.sizeof(INPUT))
            return True
        except: return False
    
    def auto_click_process(self):
        logging.info("自動點擊執行緒啟動")
        while not self.model.stop_event.is_set():
            if self.model.running:
                try:
                    screenshot = self.model.take_screenshot()
                    
                    img1_ok = self.model.find_image_on_screen(self.model.image1, screenshot)
                    img2_ok = self.model.find_image_on_screen(self.model.image2, screenshot)
                    
                    if img1_ok and img2_ok:
                        self.click_position(self.model.position_b)
                        time.sleep(0.5)
                    elif img1_ok:
                        # 分析結果
                        s5, s4, regions = self.model.analyze_stars(screenshot)
                        s3 = 10 - s5 - s4
                        
                        detected = []
                        score = 0
                        # 只有當星數達標才去識別角色 (節省效能)
                        if s5 >= self.model.min_5star:
                            detected, score, _ = self.model.detect_five_star_characters(screenshot, regions)
                        
                        success = self.model.meets_threshold(s5, s4, score)
                        self.model.record_draw(s5, s4, s3, success)
                        
                        if success:
                            msg = f"達標! 5星:{s5}, 4星:{s4}, 分數:{score}"
                            logging.info(msg)
                            if self.telegram_bot:
                                self.telegram_bot.send_success_notification_sync(screenshot, s5, s4, s3, detected)
                            
                            # 暫停並等待
                            self.model.running = False
                            while not self.model.running and not self.model.stop_event.is_set():
                                time.sleep(0.5)
                                
                            # 恢復後繼續點擊抽卡
                            if self.model.running:
                                self.click_position(self.model.position_a)
                                time.sleep(1)
                        else:
                            # 沒達標，繼續抽
                            self.click_position(self.model.position_a)
                            time.sleep(0.5)
                            
                    else:
                        # 沒看到關鍵畫面，嘗試點 SKIP 位置
                        self.click_position(self.model.position_c)
                        time.sleep(1)
                    
                    time.sleep(0.1)
                        
                except Exception as e:
                    logging.error(f"執行錯誤: {e}")
                    traceback.print_exc()
                    time.sleep(1)
            else:
                time.sleep(0.5)

class GameView:
    def show_message(self, message):
        logging.info(message)
    
    def show_error(self, error_message):
        logging.error(error_message)

if __name__ == "__main__":
    model = GameModel()
    controller = GameController(model)
    controller.start()