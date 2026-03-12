import os
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

class CharacterDetector:
    def __init__(self, get_folder_path):
        """
        初始化角色檢測器
        
        Args:
            get_folder_path: get資料夾的路徑
        """
        self.get_folder_path = Path(get_folder_path)
        self.character_templates = {}
        self.match_threshold = 0.5  # 匹配閾值，可自行修改
        self._load_character_templates()
    
    def _load_character_templates(self):
        """載入所有角色模板圖片"""
        try:
            if not self.get_folder_path.exists():
                print(f"錯誤: get資料夾不存在: {self.get_folder_path}")
                return
            
            # 遍歷get資料夾中的所有PNG檔案
            for file_path in self.get_folder_path.glob("*.png"):
                filename = file_path.stem  # 不含副檔名的檔名
                
                # 解析檔名格式: 角色名稱_分數
                if '_' in filename:
                    parts = filename.rsplit('_', 1)  # 從右邊分割一次
                    if len(parts) == 2:
                        character_name = parts[0]
                        try:
                            score = int(parts[1])
                            
                            # 使用PIL載入圖片然後轉換為OpenCV格式
                            image_pil = Image.open(file_path)
                            template = np.array(image_pil)
                            template = cv2.cvtColor(template, cv2.COLOR_RGB2BGR)
                            
                            self.character_templates[character_name] = {
                                'template': template,
                                'score': score,
                                'filename': filename
                            }
                            
                            print(f"載入角色模板: {character_name} (分數: {score})")
                            
                        except ValueError:
                            print(f"警告: 無法解析分數 - {filename}")
                    else:
                        print(f"警告: 檔名格式不正確 - {filename}")
                else:
                    print(f"警告: 檔名格式不正確 - {filename}")
            
            print(f"總共載入 {len(self.character_templates)} 個角色模板")
            
        except Exception as e:
            print(f"載入角色模板時發生錯誤: {e}")
    
    def detect_character_in_region(self, screenshot, region_coords, debug_mode=False, debug_path=None):
        """
        在指定區域中檢測角色
        
        Args:
            screenshot: 完整的螢幕截圖
            region_coords: 區域座標 (x1, y1, x2, y2)
            debug_mode: 是否啟用DEBUG模式
            debug_path: DEBUG圖片保存路徑
            
        Returns:
            tuple: (角色名稱, 分數) 或 (None, 0) 如果沒有匹配
        """
        try:
            x1, y1, x2, y2 = region_coords
            
            # 確保座標在螢幕範圍內
            h, w = screenshot.shape[:2]
            x1 = max(0, min(x1, w-1))
            y1 = max(0, min(y1, h-1))
            x2 = max(0, min(x2, w-1))
            y2 = max(0, min(y2, h-1))
            
            # 提取區域
            region = screenshot[y1:y2, x1:x2]
            
            if region.size == 0:
                return None, 0
            
            best_match = None
            best_score = 0
            best_confidence = 0
            
            # DEBUG模式：保存區域圖片
            if debug_mode and debug_path:
                region_filename = f"{debug_path}_region_{x1}_{y1}_{x2}_{y2}.png"
                cv2.imwrite(region_filename, region)
                print(f"DEBUG: 保存區域圖片 {region_filename}")
            
            # 遍歷所有角色模板進行匹配
            match_results = []
            for character_name, template_data in self.character_templates.items():
                template = template_data['template']
                score = template_data['score']
                
                # 檢查模板大小是否適合區域
                template_h, template_w = template.shape[:2]
                region_h, region_w = region.shape[:2]
                
                if template_h > region_h or template_w > region_w:
                    if debug_mode:
                        print(f"DEBUG: 模板 {character_name} 太大 ({template_w}x{template_h}) > 區域 ({region_w}x{region_h})")
                    continue  # 模板太大，跳過
                
                # 執行多種模板匹配算法進行交叉驗證
                methods = [
                    cv2.TM_CCOEFF_NORMED,
                    cv2.TM_CCORR_NORMED,
                    cv2.TM_SQDIFF_NORMED
                ]
                
                confidences = []
                locations = []
                for method in methods:
                    result = cv2.matchTemplate(region, template, method)
                    if method == cv2.TM_SQDIFF_NORMED:
                        # SQDIFF_NORMED: 值越小越好，需要轉換
                        _, min_val, _, min_loc = cv2.minMaxLoc(result)
                        confidence = 1.0 - min_val
                        locations.append(min_loc)
                    else:
                        # CCOEFF_NORMED 和 CCORR_NORMED: 值越大越好
                        _, max_val, _, max_loc = cv2.minMaxLoc(result)
                        confidence = max_val
                        locations.append(max_loc)
                    confidences.append(confidence)
                
                # 計算平均信心度，提高準確性
                avg_confidence = np.mean(confidences)
                std_confidence = np.std(confidences)
                
                # 使用第一個算法的位置作為代表位置
                best_loc = locations[0]
                
                # 如果標準差太大，表示不同算法結果差異很大，降低信心度
                if std_confidence > 0.2:
                    avg_confidence *= 0.8  # 懲罰不一致的結果
                
                match_results.append((character_name, avg_confidence, score, best_loc))
                
                if debug_mode:
                    print(f"DEBUG: {character_name} 平均匹配度: {avg_confidence:.3f} (標準差: {std_confidence:.3f}, 閾值: {self.match_threshold})")
                
                # 提高閾值要求，確保更高的準確性
                min_confidence = max(0.6, self.match_threshold)  # 至少0.6
                if avg_confidence >= min_confidence and avg_confidence > best_confidence:
                    best_match = character_name
                    best_score = score
                    best_confidence = avg_confidence
            
            # DEBUG模式：顯示所有匹配結果
            if debug_mode:
                print(f"DEBUG: 區域 ({x1},{y1})-({x2},{y2}) 所有匹配結果:")
                match_results.sort(key=lambda x: x[1], reverse=True)  # 按匹配度排序
                for name, confidence, score, loc in match_results[:5]:  # 顯示前5名
                    print(f"  {name}: {confidence:.3f} (分數: {score})")
            
            if best_match:
                print(f"檢測到角色: {best_match} (分數: {best_score}, 信心度: {best_confidence:.3f})")
                return best_match, best_score
            else:
                if debug_mode:
                    print(f"DEBUG: 區域 ({x1},{y1})-({x2},{y2}) 未找到匹配角色")
                return None, 0
                
        except Exception as e:
            print(f"角色檢測時發生錯誤: {e}")
            return None, 0
    
    def detect_characters_in_regions(self, screenshot, regions_list, debug_mode=False, debug_path=None):
        """
        在多個區域中檢測角色
        
        Args:
            screenshot: 完整的螢幕截圖
            regions_list: 區域座標列表 [(x1, y1, x2, y2), ...]
            debug_mode: 是否啟用DEBUG模式
            debug_path: DEBUG圖片保存路徑前綴
            
        Returns:
            list: [(角色名稱, 分數), ...] 的列表
        """
        detected_characters = []
        
        for i, region_coords in enumerate(regions_list):
            if debug_mode:
                print(f"DEBUG: 檢測區域 {i+1}: {region_coords}")
            
            character_name, score = self.detect_character_in_region(
                screenshot, region_coords, debug_mode, 
                f"{debug_path}_char{i+1}" if debug_path else None
            )
            
            if character_name:
                detected_characters.append((character_name, score))
            else:
                print(f"區域 {i+1}: 未檢測到已知角色")
        
        return detected_characters
    
    def calculate_total_score(self, detected_characters):
        """
        計算檢測到的角色總分數
        
        Args:
            detected_characters: [(角色名稱, 分數), ...] 的列表
            
        Returns:
            int: 總分數
        """
        return sum(score for _, score in detected_characters)
    
    def format_characters_info(self, detected_characters):
        """
        格式化角色資訊為字串
        
        Args:
            detected_characters: [(角色名稱, 分數), ...] 的列表
            
        Returns:
            str: 格式化的角色資訊字串
        """
        if not detected_characters:
            return "未檢測到已知5星角色"
        
        character_strs = [f"{name}({score}分)" for name, score in detected_characters]
        total_score = self.calculate_total_score(detected_characters)
        
        return f"獲得5星角色：{', '.join(character_strs)}，總分：{total_score}分"
