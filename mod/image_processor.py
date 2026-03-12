import cv2
import numpy as np
import logging

class ImageProcessor:
    def __init__(self, platform="windows"):
        self.platform = platform
        # 將原本散落在 main.py 的參數集中管理
        self.star_region_win = (370, 1545, 650, 675)
        self.star_region_emu = (255, 1660, 678, 700)
        self.density_thresholds_win = (25.0, 33.0)
        self.density_thresholds_emu = (30.0, 38.0)
        
        # HSV 顏色閾值 (黃色星星)
        self.lower_yellow = np.array([15, 70, 150])
        self.upper_yellow = np.array([45, 255, 255])
        self.kernel = np.ones((3, 3), np.uint8)

    def update_platform(self, platform):
        """當主程式切換平台時，同步更新這裡"""
        self.platform = platform
        logging.info(f"ImageProcessor 平台已切換為: {platform}")

    def get_star_region(self):
        return self.star_region_emu if self.platform == "emulator" else self.star_region_win

    def get_density_thresholds(self):
        return self.density_thresholds_emu if self.platform == "emulator" else self.density_thresholds_win

    def find_image(self, template, screenshot, threshold=0.8):
        """在截圖中尋找範本圖片 (通用方法)"""
        if template is None or screenshot is None:
            return False
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        return len(locations[0]) > 0

    def analyze_stars(self, screenshot, debug_mode=False, debug_path=None):
        """
        核心邏輯：分析截圖中的星星數量
        Returns: (5星數量, 4星數量, 5星區域列表)
        """
        if screenshot is None:
            return 0, 0, []

        h, w = screenshot.shape[:2]
        x1, x2, y1, y2 = self.get_star_region()
        
        # 安全檢查：確保區域不超出截圖範圍
        if y2 > h or x2 > w:
            if h > 0 and w > 0: # 避免空圖報錯
                logging.warning(f"分析區域超出邊界: screen=({w}x{h}), region=({x1},{y1},{x2},{y2})")
            return 0, 0, []

        star_region = screenshot[y1:y2, x1:x2]
        
        if debug_mode and debug_path:
            try:
                cv2.imwrite(f"{debug_path}_star_region.png", star_region)
            except Exception: pass
        
        # HSV 轉換與遮罩
        hsv = cv2.cvtColor(star_region, cv2.COLOR_BGR2HSV)
        yellow_mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
        dilated_mask = cv2.dilate(yellow_mask, self.kernel, iterations=1)
        
        # 計算切割參數
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
                # 計算對應的角色頭像區域
                char_x1 = max(0, x1 + left - 30)
                char_x2 = min(w, x1 + right + 30)
                char_y1 = max(0, y2 - 450)
                char_y2 = y2
                five_star_regions.append((char_x1, char_y1, char_x2, char_y2))
                
            star_counts.append(star_count)
        
        return star_counts.count(5), star_counts.count(4), five_star_regions