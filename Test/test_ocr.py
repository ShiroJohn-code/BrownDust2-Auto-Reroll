from paddleocr import PaddleOCR
import logging

# 設定 logging 避免雜訊
logging.getLogger("ppocr").setLevel(logging.WARNING)

def test_ocr():
    print("🚀 初始化 OCR 引擎中 (第一次執行會自動下載模型，請稍候)...")
    
    # 初始化 PaddleOCR
    # use_angle_cls=True: 自動修正文字角度
    # lang='ch': 支援中英文
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    
    img_path = 'test_sample.png'
    print(f"📸 正在讀取圖片: {img_path}")
    
    try:
        # 執行辨識
        result = ocr.ocr(img_path, cls=True)
        
        print("\n=== 辨識結果 ===")
        # result 結構通常是 [ [ [座標], (文字, 置信度) ], ... ]
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                print(f"📝 文字: {text:<20} (信心度: {confidence:.2f})")
        else:
            print("⚠️ 未偵測到任何文字")
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    test_ocr()