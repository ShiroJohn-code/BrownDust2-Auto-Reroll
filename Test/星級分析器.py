import cv2
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from PIL import Image
import glob

# 設置中文字體
try:
    # 嘗試設置微軟正黑體或其他中文字體
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False  # 解決負號顯示問題
except:
    print("無法設置中文字體，可能會導致中文顯示為方框")


def analyze_star_regions(image_path, region_x1=None, region_y1=None, region_x2=None, region_y2=None, 
                   h_min=20, h_max=40, s_min=100, s_max=255, v_min=150, v_max=255):
    """
    分析圖片中的星星區域，並用紅框標記判斷位置
    
    參數:
        image_path: 圖片路徑
        region_x1: 分析區域左上角x座標，若為None則自動偵測
        region_y1: 分析區域左上角y座標，若為None則自動偵測
        region_x2: 分析區域右下角x座標，若為None則自動偵測
        region_y2: 分析區域右下角y座標，若為None則自動偵測
        h_min: HSV色彩空間中H的最小值，用於黃色星星識別
        h_max: HSV色彩空間中H的最大值，用於黃色星星識別
        s_min: HSV色彩空間中S的最小值，用於黃色星星識別
        s_max: HSV色彩空間中S的最大值，用於黃色星星識別
        v_min: HSV色彩空間中V的最小值，用於黃色星星識別
        v_max: HSV色彩空間中V的最大值，用於黃色星星識別
    """
    # 讀取圖片
    image = cv2.imread(image_path)
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        return None
    
    # 轉換為HSV色彩空間，黃色星星在HSV中更容易識別
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 黃色的HSV範圍，包含金黃色的星星 - 使用更精確的範圍
    lower_yellow = np.array([h_min, s_min, v_min])
    upper_yellow = np.array([h_max, s_max, v_max])
    print(f"使用HSV範圍: H({h_min}-{h_max}), S({s_min}-{s_max}), V({v_min}-{v_max})")
    
    # 創建黃色遮罩
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # 取得圖片尺寸
    height, width = image.shape[:2]
    
    # 如果沒有指定分析區域，則使用預設值（整個圖片）
    if region_x1 is None or region_y1 is None or region_x2 is None or region_y2 is None:
        print("未指定分析區域，將使用自動偵測")
        region_x1 = 0
        region_y1 = int(height * 0.8)  # 預設在圖片下方20%區域尋找星星
        region_x2 = width
        region_y2 = height
    
    # 存儲每個角色的星星數量和寬度百分比
    star_counts = []
    width_percentages = []
    
    # 使用指定的分析區域
    # 將指定區域分成10等分，對應10個角色卡片
    analysis_width = region_x2 - region_x1
    segment_width = analysis_width // 10
    character_positions = [(region_x1 + i * segment_width, segment_width) for i in range(10)]
    
    # 顯示分析區域資訊
    print(f"分析區域: X1={region_x1}, Y1={region_y1}, X2={region_x2}, Y2={region_y2}")
    print(f"每個區段寬度: {segment_width}像素")
    
    # 將黃色遷罩轉換為二值圖並進行形態學操作，用於顯示
    kernel = np.ones((5,5), np.uint8)
    dilated_mask = cv2.dilate(yellow_mask, kernel, iterations=2)
    
    # 找出輪廓，僅用於顯示
    contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 篩選輪廓，只保留足夠大的輪廓
    min_contour_area = 1000  # 最小輪廓面積
    valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
    
    # 創建圖形
    plt.figure(figsize=(20, 15))
    
    # 顯示原始圖片
    plt.subplot(3, 1, 1)
    plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    plt.title("原始圖片")
    
    # 顯示黃色遮罩
    plt.subplot(3, 1, 2)
    plt.imshow(dilated_mask, cmap='gray')
    plt.title("黃色星星遮罩與偵測到的輪廓")
    
    # 在黃色遮罩上標記偵測到的輪廓
    dilated_mask_rgb = cv2.cvtColor(dilated_mask, cv2.COLOR_GRAY2RGB)
    for cnt in valid_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        cv2.rectangle(dilated_mask_rgb, (x, y), (x+w, y+h), (0, 255, 0), 2)
    
    # 創建一個彩色圖像用於顯示分析結果
    result_image = cv2.cvtColor(image.copy(), cv2.COLOR_BGR2RGB)
    
    # 分析每個角色卡片
    for i, (left, width) in enumerate(character_positions):
        # 計算當前角色卡片的邊界
        right = left + width
        
        # 提取當前區域 - 使用指定的Y座標範圍
        region = yellow_mask[region_y1:region_y2, left:right]
        
        # 將區域水平投影，得到每一列的黃色像素數量
        horizontal_projection = np.sum(region > 0, axis=0)
        
        # 找出有黃色像素的列，並計算長度
        yellow_columns = horizontal_projection > 0
        yellow_width = np.sum(yellow_columns)
        
        # 計算黃色區域的寬度作為百分比
        width_percentage = yellow_width / width * 100 if width > 0 else 0
        width_percentages.append(width_percentage)
        
        # 根據黃色區域的寬度百分比判斷星星數量
        # 寬度越大，星星數量越多
        # 綠色框中的黃色區域寬度判斷閾值
        if width_percentage < 20:  # 非常窄的黃色區域或沒有黃色
            star_count = 3
        elif width_percentage < 35:
            star_count = 4
        else:
            star_count = 5  # 長度超過閾值的都視為5星
        
        # 添加到列表
        star_counts.append(star_count)
        
        # 在結果圖片上標記判斷區域（紅框）
        cv2.rectangle(result_image, 
                     (left, region_y1), 
                     (right, region_y2), 
                     (255, 0, 0), 3)  # 紅色框
        
        # 在圖片上標記星星數量和寬度百分比
        cv2.putText(result_image, 
                   f"{star_count}★ ({width_percentage:.1f}%)", 
                   (left + 5, height - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    
    # 顯示分析結果
    plt.subplot(3, 1, 3)
    plt.imshow(result_image)
    plt.title("星星判斷結果 (紅框標記判斷區域)")
    
    # 統計3星、4星、5星的數量
    star3_count = star_counts.count(3)
    star4_count = star_counts.count(4)
    star5_count = star_counts.count(5)
    
    # 顯示結果
    plt.suptitle(f"星級分析: 3星 {star3_count}個, 4星 {star4_count}個, 5星 {star5_count}個\n各角色星級: {star_counts}")
    plt.tight_layout()
    
    # 保存結果
    result_filename = os.path.join("分析結果", os.path.basename(image_path).replace(".", "_分析."))
    os.makedirs("分析結果", exist_ok=True)
    plt.savefig(result_filename)
    
    print(f"\n===== 星級分析結果 =====")
    print(f"圖片: {image_path}")
    print(f"3星角色: {star3_count}個")
    print(f"4星角色: {star4_count}個")
    print(f"5星角色: {star5_count}個")
    print(f"各角色星級: {star_counts}")
    print(f"寬度百分比: {[f'{w:.1f}%' for w in width_percentages]}")
    print("========================")
    print(f"\n分析結果已保存為 '{result_filename}'")
    
    return {
        "3星": star3_count,
        "4星": star4_count,
        "5星": star5_count,
        "詳細": star_counts,
        "寬度百分比": width_percentages
    }

def main():
    # 獲取screenshots目錄中的所有圖片
    screenshot_files = glob.glob("screenshots/*.png")
    
    if not screenshot_files:
        print("未找到截圖文件，請確保screenshots目錄中有PNG圖片")
        return
    
    # 顯示可用的截圖文件
    print("可用的截圖文件:")
    for i, file in enumerate(screenshot_files):
        print(f"{i+1}. {file}")
    
    # 讓用戶選擇要分析的圖片
    while True:
        try:
            choice = input("\n請輸入要分析的圖片編號 (輸入q退出): ")
            if choice.lower() == 'q':
                break
                
            index = int(choice) - 1
            if 0 <= index < len(screenshot_files):
                # 讓用戶輸入分析區域
                print("\n請輸入分析區域的座標 (X1 Y1 X2 Y2)，或直接按Enter使用自動偵測:")
                region_input = input()
                
                # 讓用戶選擇是否調整HSV參數
                print("\n是否需要調整HSV參數? (y/n)，預設為n:")
                hsv_adjust = input().lower().strip() == 'y'
                
                # 分析區域參數
                region_params = {}
                if region_input.strip():
                    try:
                        x1, y1, x2, y2 = map(int, region_input.split())
                        region_params = {'region_x1': x1, 'region_y1': y1, 'region_x2': x2, 'region_y2': y2}
                    except ValueError:
                        print("座標格式錯誤，請輸入四個整數，以空格分隔")
                        continue
                
                # HSV參數
                hsv_params = {}
                if hsv_adjust:
                    try:
                        print("\n請輸入HSV參數 (預設值: H_min=20 H_max=40 S_min=100 S_max=255 V_min=150 V_max=255)")
                        print("輸入格式: H_min H_max S_min S_max V_min V_max，或直接按Enter使用預設值:")
                        hsv_input = input()
                        
                        if hsv_input.strip():
                            h_min, h_max, s_min, s_max, v_min, v_max = map(int, hsv_input.split())
                            hsv_params = {
                                'h_min': h_min, 'h_max': h_max,
                                's_min': s_min, 's_max': s_max,
                                'v_min': v_min, 'v_max': v_max
                            }
                    except ValueError:
                        print("HSV參數格式錯誤，將使用預設值")
                
                # 合併參數並分析圖片
                params = {**region_params, **hsv_params}
                analyze_star_regions(screenshot_files[index], **params)
                plt.show()  # 顯示分析結果
            else:
                print("無效的選擇，請重新輸入")
        except ValueError:
            print("請輸入有效的數字")
        except Exception as e:
            print(f"發生錯誤: {e}")

if __name__ == "__main__":
    # 確保分析結果目錄存在
    if not os.path.exists("分析結果"):
        os.makedirs("分析結果")
    main()
