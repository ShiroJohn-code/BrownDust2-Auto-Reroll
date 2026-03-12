import os
import time
import subprocess
import cv2
import numpy as np
import logging
from ppadb.client import Client as AdbClient

class LDController:
    def __init__(self, adb_path=None, serial=None):
        self.adb_path = adb_path
        self.serial = serial
        self.client = None
        self.device = None
        
        # 嘗試連接 ADB Server
        self.connect_server()
        
        # 如果有指定序號，直接鎖定該裝置
        if serial:
            self.connect_device(serial)

    def connect_server(self):
        """連接到本機的 ADB Server (Port 5037)"""
        try:
            self.client = AdbClient(host="127.0.0.1", port=5037)
            # 測試連線，如果失敗代表 Server 沒開
            self.client.version()
        except Exception:
            logging.warning("ADB Server 未啟動，嘗試啟動中...")
            if self.adb_path and os.path.exists(self.adb_path):
                try:
                    # 使用 subprocess 啟動一次 Server
                    subprocess.run([self.adb_path, "start-server"], check=True, capture_output=True)
                    time.sleep(2) # 等待啟動
                    self.client = AdbClient(host="127.0.0.1", port=5037)
                except Exception as e:
                    logging.error(f"無法啟動 ADB Server: {e}")
            else:
                logging.error("找不到 ADB 執行檔，無法啟動 Server")

    def list_devices(self):
        """列出所有已連接的裝置"""
        if not self.client:
            return {}
        
        try:
            devices = self.client.devices()
            # 回傳格式: {'serial': 'device_object'}
            return {d.serial: d for d in devices}
        except Exception as e:
            logging.error(f"獲取裝置列表失敗: {e}")
            return {}

    def connect_device(self, serial):
        """鎖定特定裝置"""
        if not self.client:
            return False
        
        try:
            self.device = self.client.device(serial)
            if self.device:
                logging.info(f"已連接裝置: {serial}")
                return True
        except Exception as e:
            logging.error(f"連接裝置 {serial} 失敗: {e}")
        return False

    def screencap(self):
        """
        [極速截圖] 直接從記憶體讀取畫面 (不寫入硬碟)
        速度比舊版快 5-10 倍
        """
        if not self.device:
            return None
        
        try:
            # 1. 獲取原始截圖數據 (bytes)
            result = self.device.screencap()
            
            # 2. 將 bytes 轉換為 numpy array
            img_array = np.frombuffer(result, np.uint8)
            
            # 3. 解碼為 OpenCV 圖片格式 (BGR)
            # 注意: screencap 預設回傳可能有表頭，cv2.imdecode 能自動處理
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            return img
        except Exception as e:
            logging.error(f"ADB 截圖失敗: {e}")
            # 如果連線斷開，嘗試重連
            self.connect_server()
            if self.serial:
                self.connect_device(self.serial)
            return None

    def tap(self, x, y):
        """執行點擊"""
        if not self.device:
            return False
        
        try:
            # 使用 shell 指令點擊
            self.device.shell(f"input tap {x} {y}")
            return True
        except Exception as e:
            logging.error(f"ADB 點擊失敗: {e}")
            return False