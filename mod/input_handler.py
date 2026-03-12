import time
import ctypes
from ctypes import wintypes
import pyautogui
import logging

# Windows API 常數 (封裝在此，不再汙染主程式)
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

class InputHandler:
    def __init__(self, model):
        self.model = model

    def click(self, position):
        """統一的點擊入口：自動判斷是模擬器還是 Windows"""
        x, y = position
        try:
            # 1. 模擬器模式
            if self.model.platform == "emulator" and self.model.ld:
                return self.model.ld.tap(x, y)
            
            # 2. Windows 模式 (優先順序: SendInput -> WinAPI -> PyAutoGUI)
            if self._send_input_click(x, y): return True
            if self._windows_api_click(x, y): return True
            
            pyautogui.click(x, y)
            return True
        except Exception as e:
            logging.error(f"點擊失敗 {position}: {e}")
            return False

    def _windows_api_click(self, x, y):
        try:
            ctypes.windll.user32.SetCursorPos(x, y)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            time.sleep(0.01)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            return True
        except: return False
    
    def _send_input_click(self, x, y):
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