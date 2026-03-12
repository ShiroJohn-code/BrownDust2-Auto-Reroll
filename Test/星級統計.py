import cv2
import numpy as np
import os
import matplotlib.pyplot as plt
from PIL import Image, ImageGrab
import keyboard
import time
import datetime

def detect_stars(image_path, show_plot=False, use_binary=True, debug=True):
    """
    檢測圖片中的星星數量並統計3星、4星、5星的數量
    使用星星區域的像素密度來判斷星星數量
    使用固定分析區域座標(370 650 1545 675)
    
    參數:
        image_path: 圖片路徑
        show_plot: 是否顯示分析結果圖形
        use_binary: 是否使用二值化處理來增強黃色星星檢測
        debug: 是否輸出詳細的調試信息
    """
    # 讀取圖片
    image = cv2.imread(image_path)
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        return None
    
    # 轉換為HSV色彩空間，黃色星星在HSV中更容易識別
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 黃色的HSV範圍，包含金黃色的星星，調整更寬的範圍以適應不同亮度條件
    lower_yellow = np.array([15, 70, 150])  # 降低H和S的下限以包含更多黃色變體
    upper_yellow = np.array([45, 255, 255])  # 提高H的上限以包含更多黃色變體
    
    print(f"使用HSV範圍: H({lower_yellow[0]}-{upper_yellow[0]}), S({lower_yellow[1]}-{upper_yellow[1]}), V({lower_yellow[2]}-{upper_yellow[2]})")
    
    # 創建黃色遮罩
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # 使用固定分析區域座標(370 650 1545 675)
    x1, y1, x2, y2 = 370, 650, 1545, 675
    
    # 從圖片中提取指定區域
    region_of_interest = image[y1:y2, x1:x2]
    region_hsv = hsv[y1:y2, x1:x2]
    region_mask = cv2.inRange(region_hsv, lower_yellow, upper_yellow)
    
    # 對黃色遮罩進行形態學操作，增強檢測效果
    kernel = np.ones((3, 3), np.uint8)
    dilated_mask = cv2.dilate(region_mask, kernel, iterations=1)
    
    # 如果啟用二值化處理，則創建一個二值化圖像用於顯示
    if use_binary:
        # 創建一個二值化圖像，只有黃色部分為白色，其餘為黑色
        binary_image = np.zeros_like(image)
        binary_image[yellow_mask > 0] = [255, 255, 255]  # 黃色區域設為白色
        
        # 提取二值化區域
        binary_roi = binary_image[y1:y2, x1:x2]
    
    # 分割區域為10個等分 (10個角色平均分佈)
    region_width = x2 - x1
    segment_width = region_width // 10
    
    # 存儲每個區域的星星數量
    star_counts = []
    width_percentages = []  # 存儲每個區域的寬度百分比，用於除錯
    
    # 創建圖形
    plt.figure(figsize=(15, 10))
    plt.subplot(2, 1, 1)
    plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    plt.title("原始圖片")
    
    # 在原圖上標記整個分析區域
    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
    
    
    # 顯示處理後的黃色遮罩
    plt.subplot(2, 1, 2)
    plt.imshow(dilated_mask, cmap='gray')
    plt.title("星星檢測區域 (黃色增強)")
    
    # 如果啟用二值化處理，則創建額外的圖形顯示二值化結果
    if use_binary:
        plt.figure(figsize=(15, 5))
        plt.imshow(cv2.cvtColor(binary_image, cv2.COLOR_BGR2RGB))
        plt.title("二值化處理結果 (僅黃色區域為白色)")
        plt.savefig("星級統計_二值化.png")
    
    # 創建一個彩色圖像用於顯示分析結果
    result_image = cv2.cvtColor(image.copy(), cv2.COLOR_BGR2RGB)
    
    # 分析每個區域
    for i in range(10):
        # 計算當前區域的邊界
        left = i * segment_width
        right = (i + 1) * segment_width
        
        # 提取當前區域，使用增強後的遮罩
        segment_mask = dilated_mask[:, left:right]
        
        # 計算當前區域中黃色像素的總數量
        yellow_pixel_count = np.sum(segment_mask > 0)
        
        # 計算區域總像素數
        total_pixels = segment_mask.shape[0] * segment_mask.shape[1]
        
        # 計算黃色像素密度百分比 - 這比單純的寬度計算更準確
        pixel_density_percentage = yellow_pixel_count / total_pixels * 100
        
        # 將區域水平投影，得到每一列的黃色像素數量
        horizontal_projection = np.sum(segment_mask > 0, axis=0)
        
        # 找出有黃色像素的列，並計算長度
        yellow_columns = horizontal_projection > 0
        yellow_width = np.sum(yellow_columns)
        
        # 計算黃色區域的寬度作為百分比
        width_percentage = yellow_width / segment_width * 100
        
        # 計算垂直方向的投影
        vertical_projection = np.sum(segment_mask > 0, axis=1)
        yellow_rows = vertical_projection > 0
        yellow_height = np.sum(yellow_rows)
        height_percentage = yellow_height / segment_mask.shape[0] * 100
        
        # 綜合考慮寬度、高度和密度
        # 存儲寬度百分比和像素密度百分比供判斷用
        width_percentages.append({
            "寬度": width_percentage,
            "高度": height_percentage,
            "密度": pixel_density_percentage
        })
        
        # 使用像素密度來判斷星星數量
        # 根據實際測試結果調整閾值
        density = pixel_density_percentage
        
        # 根據實際測試結果調整閾值
        # 3星密度約為18-19%
        # 4星密度約為24-25%
        # 5星密度約為30-31%
        if density < 20:  # 3星角色 - 密度約18-19%
            star_count = 3
        elif density < 28:  # 4星角色 - 密度約24-25%
            star_count = 4
        else:  # 5星角色 - 密度約30-31%
            star_count = 5
            
        # 輸出詳細的判斷依據，用於調試
        print(f"區域 {i+1}: 寬度={width_percentage:.1f}%, 高度={height_percentage:.1f}%, 密度={pixel_density_percentage:.1f}%, 判斷為{star_count}星")
        
        # 添加到列表
        star_counts.append(star_count)
        
        # 在圖片上標記星星數量和密度百分比
        cv2.putText(image, f"{star_count}★ ({pixel_density_percentage:.1f}%)", 
                    (x1 + left + 10, y1 + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # 在圖片上畫出分析區域 - 使用綠色細線框
        cv2.rectangle(image, (x1 + left, y1), (x1 + right, y2), (0, 255, 0), 1)
        
        # 在結果圖像上畫出更明顯的紅色框
        cv2.rectangle(result_image, (x1 + left, y1), (x1 + right, y2), (255, 0, 0), 3)
    
    # 統計3星、4星、5星的數量
    star3_count = star_counts.count(3)
    star4_count = star_counts.count(4)
    star5_count = star_counts.count(5)
    
    # 輸出總體統計結果
    print(f"\n總計: 3星 {star3_count}個, 4星 {star4_count}個, 5星 {star5_count}個")
    
    # 創建一個新的子圖用於顯示分析結果
    plt.figure(figsize=(15, 10))
    
    # 顯示原始圖片和分析結果
    plt.subplot(2, 1, 1)
    plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    plt.title("原始圖片與分析區域")
    
    # 顯示分析結果圖像
    plt.subplot(2, 1, 2)
    plt.imshow(result_image)
    plt.title("星星判斷結果 (紅框標記判斷區域)")
    
    # 創建密度分布圖
    plt.figure(figsize=(15, 5))
    densities = [data['密度'] for data in width_percentages]
    plt.bar(range(1, 11), densities)
    plt.axhline(y=20, color='r', linestyle='--', label='3星閾值')
    plt.axhline(y=28, color='g', linestyle='--', label='4星閾值')
    plt.xlabel('區域編號')
    plt.ylabel('像素密度 (%)')
    plt.title('各區域像素密度分布')
    plt.legend()
    plt.savefig('星級密度分布.png')
    
    # 顯示結果
    plt.suptitle(f"星級統計: 3星 {star3_count}個, 4星 {star4_count}個, 5星 {star5_count}個")
    plt.tight_layout()
    plt.savefig("星級統計結果.png")
    
    # 只在主線程中顯示圖形
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return {
        "3星": star3_count,
        "4星": star4_count,
        "5星": star5_count,
        "詳細": star_counts,
        "寬度百分比": width_percentages  # 添加綜合數據供除錯用
    }

def take_screenshot():
    """
    截取全螢幕畫面並保存
    """
    # 創建保存截圖的目錄
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    
    # 生成檔案名稱，包含時間戳
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"screenshots/screenshot_{timestamp}.png"
    
    # 截取全螢幕
    print("正在截取螢幕...")
    try:
        # 使用PIL的ImageGrab而不是pyautogui
        screenshot = ImageGrab.grab()
        screenshot.save(screenshot_path)
        print(f"截圖已保存: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f"截圖失敗: {e}")
        return None

def on_f10_pressed():
    """
    當按下F10時執行的函數
    """
    print("\n按下F10，開始截圖並分析...")
    
    # 截取螢幕
    screenshot_path = take_screenshot()
    
    if screenshot_path:
        # 分析圖片，不顯示圖形介面，啟用二值化處理
        result = detect_stars(screenshot_path, show_plot=False, use_binary=True)
        
        if result:
            print("\n===== 星級統計結果 =====")
            print(f"3星角色: {result['3星']}個")
            print(f"4星角色: {result['4星']}個")
            print(f"5星角色: {result['5星']}個")
            print(f"各角色星級: {result['詳細']}")
            # 輸出更詳細的分析數據
            print("各區域詳細分析:")
            for i, data in enumerate(result['寬度百分比']):
                star_label = "★" * result['詳細'][i]  # 根據星級顯示星星符號
                print(f"  區域 {i+1}: 寬度={data['寬度']:.1f}%, 高度={data['高度']:.1f}%, 密度={data['密度']:.1f}% -> {result['詳細'][i]}星 {star_label}")
            print("========================")
            print("\n結果已保存為 '星級統計結果.png'")
            print("二值化處理結果已保存為 '星級統計_二值化.png'")
            print("密度分布圖已保存為 '星級密度分布.png'")
    else:
        print("截圖失敗，無法分析星級")

def analyze_existing_screenshots():
    """
    分析已存在的截圖
    """
    # 檢查screenshots目錄是否存在
    if not os.path.exists("screenshots"):
        print("找不到screenshots目錄，請先截圖")
        return
    
    # 獲取所有截圖檔案
    screenshots = [f for f in os.listdir("screenshots") if f.endswith(".png")]
    
    if not screenshots:
        print("找不到任何截圖，請先截圖")
        return
    
    # 按照檔名排序（通常包含時間戳）
    screenshots.sort()
    
    # 顯示所有截圖供選擇
    print("\n可用的截圖:")
    for i, screenshot in enumerate(screenshots):
        print(f"{i+1}. {screenshot}")
    
    # 讓使用者選擇截圖
    try:
        choice = int(input("\n請選擇要分析的截圖編號 (輸入數字): "))
        if choice < 1 or choice > len(screenshots):
            print("無效的選擇")
            return
        
        # 分析選擇的截圖
        screenshot_path = os.path.join("screenshots", screenshots[choice-1])
        print(f"\n分析截圖: {screenshot_path}")
        
        # 詢問是否使用二值化處理
        use_binary = input("是否使用二值化處理來增強黃色星星檢測? (y/n): ").lower() == 'y'
        
        # 分析圖片
        result = detect_stars(screenshot_path, show_plot=False, use_binary=use_binary)
        
        if result:
            print("\n===== 星級統計結果 =====")
            print(f"3星角色: {result['3星']}個")
            print(f"4星角色: {result['4星']}個")
            print(f"5星角色: {result['5星']}個")
            print(f"各角色星級: {result['詳細']}")
            # 輸出更詳細的分析數據
            print("各區域詳細分析:")
            for i, data in enumerate(result['寬度百分比']):
                star_label = "★" * result['詳細'][i]  # 根據星級顯示星星符號
                print(f"  區域 {i+1}: 寬度={data['寬度']:.1f}%, 高度={data['高度']:.1f}%, 密度={data['密度']:.1f}% -> {result['詳細'][i]}星 {star_label}")
            print("========================")
            print("\n結果已保存為 '星級統計結果.png'")
            if use_binary:
                print("二值化處理結果已保存為 '星級統計_二值化.png'")
    except ValueError:
        print("請輸入有效的數字")

def main():
    # 註冊F10快捷鍵
    keyboard.add_hotkey('f10', on_f10_pressed)
    
    print("程式已啟動！")
    print("選項 1: 按F10鍵自動截圖並分析星級 (使用二值化處理)")
    print("選項 2: 分析已存在的截圖 (可選擇是否使用二值化處理)")
    print("分析結果會保存為圖片並顯示在終端機中")
    print("二值化處理會將黃色星星區域轉為白色，其餘區域為黑色，提高檢測準確度")
    print("星級判斷標準: 密度<20% 為3星, 20-28% 為4星, >28% 為5星")
    print("按Ctrl+C結束程式")
    
    # 先詢問是否要分析已有的截圖
    analyze_existing = input("\n是否要分析已有的截圖? (y/n): ").lower()
    if analyze_existing == 'y':
        analyze_existing_screenshots()
    
    # 保持程式運行
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("程式已結束")

if __name__ == "__main__":
    # 確保截圖目錄存在
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")
    main()
