import ctypes
import ctypes.wintypes
import logging
import numpy as np
import cv2
import mss


class WindowTracker:
    """追蹤遊戲視窗位置與大小，動態換算座標與截圖區域。"""

    BASE_WIDTH = 1920
    BASE_HEIGHT = 1080

    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = None

    def find(self) -> bool:
        """用 FindWindowW 尋找視窗，成功時儲存 hwnd 並回傳 True。"""
        hwnd = ctypes.windll.user32.FindWindowW(None, self.window_title)
        if hwnd:
            self.hwnd = hwnd
            logging.info(f"找到遊戲視窗: '{self.window_title}' (hwnd={hwnd})")
            return True
        self.hwnd = None
        return False

    def is_available(self) -> bool:
        """
        檢查視窗 hwnd 是否有效（存在即可，最小化由 bring_to_front 處理）。
        hwnd 失效時自動呼叫 find() 重試，處理遊戲重啟場景。
        """
        if self.hwnd is None:
            return self.find()

        user32 = ctypes.windll.user32
        if not user32.IsWindow(self.hwnd):
            return self.find()

        return True

    def bring_to_front(self) -> bool:
        """
        將視窗還原（若最小化）並拉到前景。
        使用 AttachThreadInput 繞過 Windows 前景鎖定。
        回傳是否成功。
        """
        if not self.hwnd:
            return False
        try:
            user32   = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # 若最小化先還原
            if user32.IsIconic(self.hwnd):
                user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE

            # AttachThreadInput 技巧：借用前景執行緒的輸入權限
            fg_hwnd   = user32.GetForegroundWindow()
            fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
            my_thread = kernel32.GetCurrentThreadId()

            if fg_thread and fg_thread != my_thread:
                user32.AttachThreadInput(fg_thread, my_thread, True)
                user32.SetForegroundWindow(self.hwnd)
                user32.BringWindowToTop(self.hwnd)
                user32.AttachThreadInput(fg_thread, my_thread, False)
            else:
                user32.SetForegroundWindow(self.hwnd)
                user32.BringWindowToTop(self.hwnd)

            return True
        except Exception as e:
            logging.warning(f"bring_to_front 失敗: {e}")
            return False

    def get_client_screen_rect(self):
        """
        取得視窗 client area 在螢幕上的絕對位置。
        回傳 (left, top, width, height) 或 None（失敗時）。
        """
        if not self.hwnd:
            return None
        try:
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetClientRect(self.hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return None

            pt = ctypes.wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
            return (pt.x, pt.y, w, h)
        except Exception as e:
            logging.warning(f"get_client_screen_rect 失敗: {e}")
            return None

    def scale_position(self, base_x: int, base_y: int):
        """
        將 1920x1080 基準座標換算為螢幕絕對座標。
        失敗時回傳 None，讓呼叫端做 fallback。
        """
        rect = self.get_client_screen_rect()
        if rect is None:
            return None
        left, top, w, h = rect
        screen_x = left + int(base_x * w / self.BASE_WIDTH)
        screen_y = top  + int(base_y * h / self.BASE_HEIGHT)
        return (screen_x, screen_y)

    def capture(self):
        """
        截取視窗 client area，結果統一 resize 到 1920x1080 BGR ndarray。
        失敗時回傳 None。
        """
        rect = self.get_client_screen_rect()
        if rect is None:
            return None
        left, top, w, h = rect
        if w <= 0 or h <= 0:
            return None
        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": w, "height": h}
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                if w != self.BASE_WIDTH or h != self.BASE_HEIGHT:
                    img = cv2.resize(img, (self.BASE_WIDTH, self.BASE_HEIGHT),
                                     interpolation=cv2.INTER_AREA)
                return img
        except Exception as e:
            logging.warning(f"window_tracker.capture 失敗: {e}")
            return None
