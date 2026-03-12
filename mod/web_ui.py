import cv2
import time
import threading
import logging
import socket
import secrets
import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, Response, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# 定義資料模型
class ConfigPayload(BaseModel):
    min_5star: int
    min_4star: int

class SystemPayload(BaseModel):
    monitor_index: int

class TelegramPayload(BaseModel):
    token: str
    chat_id: str

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>登入 - Gacha Control Panel</title>
<style>
body{background:#121212;color:#e0e0e0;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
.login-box{background:#1e1e1e;border:1px solid #333;border-radius:12px;padding:40px 30px;width:320px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.5)}
h2{margin:0 0 8px;font-size:1.4rem}
.subtitle{color:#888;font-size:0.85rem;margin-bottom:24px}
input[type=password]{width:100%;padding:12px;background:#2c2c2c;border:1px solid #444;border-radius:8px;color:#fff;font-size:1rem;box-sizing:border-box;margin-bottom:16px}
input[type=password]:focus{outline:none;border-color:#0d6efd}
button{width:100%;padding:12px;background:#0d6efd;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;transition:background .2s}
button:hover{background:#0b5ed7}
.error{color:#dc3545;font-size:0.85rem;margin-bottom:12px}
.lock-msg{color:#dc3545;font-size:0.9rem;margin-top:12px}
</style></head><body>
<div class="login-box">
<h2>🔒 控制台登入</h2>
<p class="subtitle">Gacha Automation Panel</p>
{error}
<form method="POST" action="/login">
<input type="password" name="password" placeholder="請輸入密碼" autofocus required>
<button type="submit">登入</button>
</form>
{lock_msg}
</div></body></html>"""

MAX_FAILURES = 3
BAN_SECONDS = 3600

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def is_ip_banned(auth_state: dict, ip: str) -> bool:
    until = auth_state["ban_until"].get(ip, 0)
    if until and time.time() < until:
        return True
    if until and time.time() >= until:
        auth_state["ban_until"].pop(ip, None)
        auth_state["fail_count"].pop(ip, None)
    return False

def update_ban_state(auth_state: dict, ip: str):
    auth_state["fail_count"][ip] = auth_state["fail_count"].get(ip, 0) + 1
    if auth_state["fail_count"][ip] >= MAX_FAILURES:
        auth_state["ban_until"][ip] = time.time() + BAN_SECONDS

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, password: str, session_tokens: set, auth_state: dict):
        super().__init__(app)
        self.password = password
        self.session_tokens = session_tokens
        self.auth_state = auth_state

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/login":
            return await call_next(request)

        ip = get_client_ip(request)
        if is_ip_banned(self.auth_state, ip):
            remaining = int(self.auth_state["ban_until"][ip] - time.time())
            lock_msg = f'<p class="lock-msg">⛔ IP 已被封鎖，請在 {remaining // 60} 分鐘後重試</p>'
            return HTMLResponse(LOGIN_PAGE_HTML.format(error="", lock_msg=lock_msg), status_code=403)

        token = request.cookies.get("session_token")
        if token and token in self.session_tokens:
            return await call_next(request)

        return RedirectResponse(url="/login", status_code=302)

class WebController:
    def __init__(self, model, controller):
        self.model = model
        self.controller = controller
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory="templates")
        
        self.port = 8964
        self.local_ip = self.get_local_ip()
        self.public_ip = self.get_public_ip()

        # Cookie 驗證 (密碼 + IP 封鎖)
        self.auth_pass = self.model.config.get('WebUI', 'password', fallback='admin')
        self.session_tokens: set[str] = set()
        self.auth_state = {"fail_count": {}, "ban_until": {}}
        self.app.add_middleware(AuthMiddleware, password=self.auth_pass, session_tokens=self.session_tokens, auth_state=self.auth_state)

        # === 註冊路由 ===
        self.app.get("/login")(self.login_page)
        self.app.post("/login")(self.login_submit)
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
        except Exception: return "127.0.0.1"

    def get_public_ip(self):
        try:
            response = requests.get('https://api.ipify.org', timeout=3)
            if response.status_code == 200: return response.text
        except Exception: pass
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

    async def login_page(self, request: Request):
        ip = get_client_ip(request)
        if is_ip_banned(self.auth_state, ip):
            remaining = int(self.auth_state["ban_until"][ip] - time.time())
            lock_msg = f'<p class="lock-msg">⛔ IP 已被封鎖，請在 {remaining // 60} 分鐘後重試</p>'
            return HTMLResponse(LOGIN_PAGE_HTML.format(error="", lock_msg=lock_msg), status_code=403)
        return HTMLResponse(LOGIN_PAGE_HTML.format(error="", lock_msg=""))

    async def login_submit(self, request: Request, password: str = Form(...)):
        ip = get_client_ip(request)
        if is_ip_banned(self.auth_state, ip):
            remaining = int(self.auth_state["ban_until"][ip] - time.time())
            lock_msg = f'<p class="lock-msg">⛔ IP 已被封鎖，請在 {remaining // 60} 分鐘後重試</p>'
            return HTMLResponse(LOGIN_PAGE_HTML.format(error="", lock_msg=lock_msg), status_code=403)

        if secrets.compare_digest(password, self.auth_pass):
            token = secrets.token_hex(32)
            self.session_tokens.add(token)
            self.auth_state["fail_count"].pop(ip, None)
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie("session_token", token, httponly=True, max_age=86400)
            logging.info(f"Web UI: IP {ip} 登入成功")
            return response

        self.auth_state["fail_count"][ip] = self.auth_state["fail_count"].get(ip, 0) + 1
        if self.auth_state["fail_count"][ip] >= MAX_FAILURES:
            self.auth_state["ban_until"][ip] = time.time() + BAN_SECONDS
            logging.warning(f"Web UI: IP {ip} 連續驗證失敗 {MAX_FAILURES} 次，封鎖 1 小時")
            lock_msg = '<p class="lock-msg">⛔ 密碼錯誤次數過多，IP 已被封鎖 1 小時</p>'
            return HTMLResponse(LOGIN_PAGE_HTML.format(error="", lock_msg=lock_msg), status_code=403)
        error_html = '<p class="error">❌ 密碼錯誤，請重試</p>'
        return HTMLResponse(LOGIN_PAGE_HTML.format(error=error_html, lock_msg=""), status_code=401)

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
                "tg_token": (tg_token[:6] + "***") if len(tg_token) > 6 else "未設定",
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
        self.model.set_thresholds(payload.min_5star, payload.min_4star)
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