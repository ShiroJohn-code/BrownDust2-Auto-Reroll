import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

# 導入專案內的 GameModel
from main import GameModel


def load_bgr_image(path: str) -> np.ndarray:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到檔案: {path}")
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"讀取圖片失敗: {path}")
    return img  # BGR


def main():
    parser = argparse.ArgumentParser(description="Analyze star regions from a screenshot using GameModel.analyze_stars")
    parser.add_argument("--image", required=True, help="輸入圖片路徑 (建議為 1920x1080 截圖)")
    parser.add_argument("--debug-prefix", default=None, help="輸出除錯圖片與區域的檔名前綴，例如 screenshots/test_debug")
    args = parser.parse_args()

    # 讀圖 (BGR)
    screenshot = load_bgr_image(args.image)

    # 建立 GameModel 實例（不需要啟動整個程式，只用分析功能）
    gm = GameModel()

    # 進行分析
    debug_mode = args.debug_prefix is not None
    stars_5, stars_4, five_star_regions = gm.analyze_stars(
        screenshot, debug_mode=debug_mode, debug_path=args.debug_prefix
    )

    stars_3 = 10 - stars_5 - stars_4

    print("=== 分析結果 ===")
    print(f"5星: {stars_5}, 4星: {stars_4}, 3星: {stars_3}")
    print(f"5星區域數量: {len(five_star_regions)}")
    for i, (x1, y1, x2, y2) in enumerate(five_star_regions, start=1):
        print(f"  區域 {i}: ({x1}, {y1}) -> ({x2}, {y2})")

    # 額外：在輸入圖上可視化星級主區域與每個角色分區（與 F9 顯示一致）
    debug_vis = screenshot.copy()
    star_region_y1 = 678
    star_region_y2 = 700
    star_region_x1 = 255
    star_region_x2 = 1660
    cv2.rectangle(debug_vis, (star_region_x1, star_region_y1), (star_region_x2, star_region_y2), (255, 0, 0), 2)
    cv2.putText(debug_vis, "Star Analysis Region", (star_region_x1, star_region_y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    region_width = star_region_x2 - star_region_x1
    gap_width = 25
    total_gaps = 9 * gap_width
    effective_width = region_width - total_gaps
    segment_width = effective_width // 10

    for i in range(10):
        left = i * (segment_width + gap_width)
        right = left + segment_width
        x_left = star_region_x1 + left
        cv2.line(debug_vis, (x_left, star_region_y1), (x_left, star_region_y2), (0, 255, 0), 2)
        if i == 9:
            x_right = star_region_x1 + right
            cv2.line(debug_vis, (x_right, star_region_y1), (x_right, star_region_y2), (0, 255, 0), 2)
        center_x = x_left + segment_width // 2
        cv2.putText(debug_vis, f"{i+1}", (center_x - 10, star_region_y1 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if five_star_regions:
        for i, (x1, y1, x2, y2) in enumerate(five_star_regions, start=1):
            cv2.rectangle(debug_vis, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(debug_vis, f"5★-{i}", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # 輸出可視化
    out_dir = Path("screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "analyze_vis.png"
    cv2.imwrite(str(out_path), debug_vis)
    print(f"可視化結果已輸出: {out_path}")


if __name__ == "__main__":
    main()
