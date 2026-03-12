import os
import io
import cv2
import threading
import uvicorn
import logging
import time
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

class WebController:
    def __init__(self, game_model, game_controller):
        self.model = game_model
        self.controller = game_controller
        
        # 讀取設定
        self.host = "0.0.0.0" # 開放外網連線
        self.port = 8080      # 預設 Port
        
        # 初始化 FastAPI
        self.app = FastAPI()
        self.setup_routes()
        
        # 設定模板目錄
        template_dir = os.path.join(self.model.script_dir, "templates")
        if not os.path.exists(template_dir):
            os.makedirs(template_dir)
        self.templates = Jinja2Templates(directory=template_dir)

    def setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def home(request: Request):
            """渲染主頁面"""
            return self.templates.TemplateResponse("index.html", {
                "request": request,
                "config": {
                    "min_5star": self.model.min_5star,
                    "min_4star": self.model.min_4star,
                    "min_score": self.model.min_score
                }
            })

        @self.app.get("/api/status")
        async def get_status():
            """API: 獲取即時狀態 (供前端 AJAX 輪詢)"""
            stats = self.model.get_draw_statistics()
            return {
                "running": self.model.running,
                "draw_count": self.model.draw_count,
                "stats": stats,
                "platform": self.model.platform
            }

        @self.app.post("/api/action")
        async def action(action: str = Form(...)):
            """API: 控制開始/暫停"""
            if action == "start":
                self.model.running = True
                logging.info("[Web] 觸發啟動")
            elif action == "stop":
                self.model.running = False
                logging.info("[Web] 觸發暫停")
            return {"status": "ok", "running": self.model.running}

        @self.app.post("/api/config")
        async def update_config(
            min_5star: int = Form(...),
            min_4star: int = Form(...),
            min_score: int = Form(...)
        ):
            """API: 更新設定"""
            self.model.set_thresholds(min_5star, min_4star, min_score)
            logging.info(f"[Web] 設定已更新: 5★>={min_5star}, 4★>={min_4star}, 分數>={min_score}")
            return {"status": "ok"}

        @self.app.get("/video_feed")
        async def video_feed():
            """即時影像串流 (MJPEG)"""
            return StreamingResponse(self.generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    def generate_frames(self):
        """
        生成影像串流的生成器 (修正版：解決 Race Condition)
        """
        last_processed_time = 0
        
        while True:
            frame = None
            
            # 策略：根據運行狀態決定影像來源
            if self.model.running:
                # 1. 掛機中 (Running): 使用「被動快取模式」
                # 只讀取主程式產生的最新畫面，絕不主動截圖，避免搶佔 ADB/CPU
                with self.model.frame_lock:
                    if self.model.latest_frame is not None:
                        frame = self.model.latest_frame.copy() # 複製一份以免影響主執行緒
            else:
                # 2. 暫停中 (Stopped): 使用「主動截圖模式」
                # 因為主程式沒在跑，Web 介面負責截圖。限制 FPS 以節省資源。
                current_time = time.time()
                if current_time - last_processed_time > 0.5: # 限制為 2 FPS (每0.5秒一次)
                    frame = self.model.take_screenshot()
                    last_processed_time = current_time

            if frame is None:
                time.sleep(0.1)
                continue
            
            try:
                # 壓縮圖片以降低網路延遲
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception:
                pass
            
            # 控制串流更新頻率
            time.sleep(0.1)

    def start(self):
        """在獨立執行緒啟動伺服器"""
        def run_server():
            # 隱藏 Uvicorn 的 Log，避免干擾我們自己的 Log
            log_config = uvicorn.config.LOGGING_CONFIG
            log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
            
            logging.info(f"Web 控制台已啟動: http://localhost:{self.port}")
            uvicorn.run(self.app, host=self.host, port=self.port, log_config=log_config)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()