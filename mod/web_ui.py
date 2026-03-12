import cv2
import time
import threading
import logging
import socket
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# 定義資料模型
class ConfigPayload(BaseModel):
    min_5star: int
    min_4star: int
    min_score: int

class SystemPayload(BaseModel):
    monitor_index: int

class TelegramPayload(BaseModel):
    token: str
    chat_id: str

class WebController:
    def __init__(self, model, controller):
        self.model = model
        self.controller = controller
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory="templates")
        
        self.port = 8964
        self.local_ip = self.get_local_ip()
        self.public_ip = self.get_public_ip()

        # === 註冊路由 ===
        self.app.get("/")(self.index)
        
        # [關鍵修正] 改用 snapshot API，移除 video_feed
        self.app.get("/api/snapshot")(self.get_snapshot)
        
        # 其他 API
        self.app.get("/api/stats")(self.get_stats)          
        self.app.post("/api/toggle")(self.toggle_running)   
        self.app.post("/api/config")(self.update_config)    
        self.app.post("/api/system")(self.update_system)    
        self.app.post("/api/telegram")(self.update_telegram)
        self.app.post("/api/reset")(self.reset_stats)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: return "127.0.0.1"

    def get_public_ip(self):
        try:
            response = requests.get('https://api.ipify.org', timeout=3)
            if response.status_code == 200: return response.text
        except: pass
        return "無法獲取"

    def start(self):
        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        try:
            logging.info(f"Web 控制台啟動中: http://{self.local_ip}:{self.port}")
            if self.public_ip != "無法獲取":
                logging.info(f"外網訪問地址: http://{self.public_ip}:{self.port}")
            config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="critical")
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            logging.error(f"Web Server 啟動失敗: {e}")

    # === 路由實作 ===

    async def index(self, request: Request):
        return self.templates.TemplateResponse("index.html", {
            "request": request
        })

    # [關鍵修正] 單張快照 API (取代原本的串流)
    async def get_snapshot(self):
        """回傳當前畫面的單張 JPEG 快照"""
        if self.model.latest_frame is None:
            # 如果還沒截圖，回傳 204 No Content (前端不會報錯)
            return Response(status_code=204)
            
        try:
            # 加上鎖，避免讀取時發生寫入衝突
            with self.model.frame_lock:
                frame = self.model.latest_frame.copy()
            
            # 壓縮圖片 (品質 50，追求極速)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            ret, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            if not ret: return Response(status_code=500)
                
            return Response(content=buffer.tobytes(), media_type="image/jpeg")
        except Exception:
            return Response(status_code=500)

    # === API 實作 ===

    async def get_stats(self):
        stats = self.model.get_draw_statistics()
        dist = self.model.get_five_star_distribution()
        
        platform_str = "Windows 桌面"
        if self.model.platform == "emulator":
            platform_str = f"模擬器 ({self.model.adb_serial})"

        tg_token = self.model.config.get('Telegram', 'token', fallback="")
        tg_chat_id = self.model.config.get('Telegram', 'chat_id', fallback="")

        return JSONResponse({
            "running": self.model.running,
            "total_draws": stats["total_draws"],
            "avg_5star": stats["avg_5star"],
            "avg_4star": stats["avg_4star"],
            "success_rate": stats["success_rate"],
            "distribution": dist,
            "config": {
                "min_5star": self.model.min_5star,
                "min_4star": self.model.min_4star,
                "min_score": self.model.min_score,
                "tg_token": tg_token,
                "tg_chat_id": tg_chat_id,
                "monitor_index": self.model.monitor_index
            },
            "system_info": {
                "local_ip": f"{self.local_ip}:{self.port}",
                "public_ip": f"{self.public_ip}:{self.port}",
                "platform": platform_str
            }
        })

    async def toggle_running(self):
        self.controller.toggle_program()
        return JSONResponse({"status": "ok", "running": self.model.running})

    async def reset_stats(self):
        self.model.reset_statistics()
        return JSONResponse({"status": "ok", "message": "統計數據已歸零"})

    async def update_config(self, payload: ConfigPayload):
        self.model.set_thresholds(payload.min_5star, payload.min_4star, payload.min_score)
        return JSONResponse({"status": "ok"})

    async def update_system(self, payload: SystemPayload):
        self.model.set_system_config(payload.monitor_index)
        return JSONResponse({"status": "ok"})

    async def update_telegram(self, payload: TelegramPayload):
        if not self.model.config.has_section('Telegram'):
            self.model.config.add_section('Telegram')
        self.model.config.set('Telegram', 'token', payload.token)
        self.model.config.set('Telegram', 'chat_id', payload.chat_id)
        with open(self.model.config_path, 'w', encoding='utf-8') as f:
            self.model.config.write(f)
        self.controller.reload_telegram_bot()
        return JSONResponse({"status": "ok"})