"""
Telegram Bot 模組 - 用於遠端控制抽卡程式
修正版：解決執行緒衝突與 Event Loop 問題
"""

import asyncio
import io
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Conflict
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

class TelegramController:
    def __init__(self, token, chat_id, game_model, game_controller):
        self.token = token
        self.chat_id = chat_id
        self.game_model = game_model
        self.game_controller = game_controller
        self.bot = None
        self.application = None
        self.is_running = False
        self.bot_thread = None
        self.last_notification_message_id = None
        # 新增：保存 Bot 運行所在的 Event Loop
        self.loop = None
        
    def start_bot_thread(self):
        """在新線程中啟動 bot (修正版)"""
        def run_bot():
            try:
                # 創建新的事件循環並保存到 self.loop
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                # 創建應用程式
                self.application = Application.builder().token(self.token).build()
                
                # 註冊處理器
                self.application.add_handler(CommandHandler("start", self.start_command))
                self.application.add_handler(CommandHandler("status", self.status_command))
                self.application.add_handler(CommandHandler("stats", self.stats_command))
                self.application.add_handler(CommandHandler("distribution", self.distribution_command))
                self.application.add_handler(CallbackQueryHandler(self.button_callback))
                # 註冊錯誤處理器
                self.application.add_error_handler(self.error_handler)
                
                self.bot = self.application.bot
                self.is_running = True
                
                print("Telegram Bot 正在啟動 (Thread Safe Mode)...")
                
                # 使用 run_polling，它會阻塞直到停止
                self.application.run_polling(close_loop=False)
                
            except Exception as e:
                print(f"Telegram Bot 啟動失敗: {e}")
                self.is_running = False
            finally:
                print("Telegram Bot 線程已結束")
            
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        
        # 等待一下讓 Bot 啟動
        time.sleep(2)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """處理 Bot 運行時的錯誤"""
        print(f"Telegram Bot 錯誤: {context.error}")
        if isinstance(context.error, Conflict):
            print("檢測到 Conflict 錯誤：可能是多個 Bot 實例同時運行。")
            self.is_running = False
            # 可以在這裡觸發程式暫停或退出

    async def stop_bot(self):
        """停止 Telegram Bot"""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                print(f"停止 Bot 時發生錯誤: {e}")
        self.is_running = False

    def stop_bot_sync(self):
        """同步停止 Bot"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.stop_bot(), self.loop)

        
    # --- 命令處理器 ---
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = (
            "🎯 **無限抽自動化程式遠端控制**\n\n"
            f"{self.get_overview_text()}\n\n"
            "請選擇要執行的操作："
        )
        await update.message.reply_text(welcome_text, reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.get_overview_text(), reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.get_overview_text(), reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

    async def distribution_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.get_overview_text(), reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "toggle_draw":
            if self.game_model.running:
                self.game_model.running = False
                status_msg = "⏸️ **抽卡已暫停！**"
            else:
                self.game_model.running = True
                status_msg = "🎮 **抽卡已開始！**"
            await query.edit_message_text(f"{status_msg}\n\n{self.get_overview_text()}", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
        
        elif query.data == "check_overview":
            await query.edit_message_text(self.get_overview_text(), reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
            
        elif query.data == "settings":
            await query.edit_message_text(self.get_settings_text(), reply_markup=self.get_settings_keyboard(), parse_mode='Markdown')

        elif query.data == "noop":
            return

        elif query.data == "refresh":
            await query.edit_message_text(f"🔄 **主選單**\n\n{self.get_overview_text()}", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')

        elif query.data.startswith("set_5star_"):
            val = int(query.data.split("_")[-1])
            new_val = max(0, self.game_model.min_5star + val)
            self.game_model.set_thresholds(new_val, self.game_model.min_4star)
            await query.edit_message_text(self.get_settings_text(), reply_markup=self.get_settings_keyboard(), parse_mode='Markdown')

        elif query.data.startswith("set_4star_"):
            val = int(query.data.split("_")[-1])
            new_val = max(0, self.game_model.min_4star + val)
            self.game_model.set_thresholds(self.game_model.min_5star, new_val)
            await query.edit_message_text(self.get_settings_text(), reply_markup=self.get_settings_keyboard(), parse_mode='Markdown')
            
        elif query.data == "reset_data":
            self.game_model.draw_count = 0
            self.game_model.draw_records.clear()
            try:
                with open(self.game_model.log_file, "w", encoding="utf-8") as f:
                    f.write("=== 抽卡紀錄 ===\n\n")
            except Exception:
                pass
            await query.edit_message_text("✅ **數據已重置！**\n\n抽卡紀錄已清除，從 0 開始重新計算。", reply_markup=self.get_settings_keyboard(), parse_mode='Markdown')

        elif query.data == "continue_draw":
            self.game_model.running = True
            try:
                await query.edit_message_text("✅ **繼續抽卡！**\n\n已確認結果，繼續進行抽卡...", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
                self.last_notification_message_id = query.message.message_id
            except Exception:
                msg = await self.bot.send_message(chat_id=self.chat_id, text="✅ **繼續抽卡！**\n\n已確認結果，繼續進行抽卡...", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
                self.last_notification_message_id = msg.message_id
            
        elif query.data == "stop_draw":
            self.game_model.running = False
            try:
                await query.edit_message_text("🛑 **停止抽卡！**\n\n已停止抽卡程式。", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
                self.last_notification_message_id = query.message.message_id
            except Exception:
                msg = await self.bot.send_message(chat_id=self.chat_id, text="🛑 **停止抽卡！**\n\n已停止抽卡程式。", reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
                self.last_notification_message_id = msg.message_id

    # --- 輔助方法 (鍵盤與文字生成) ---
    def get_main_keyboard(self):
        toggle_text = "⏸️ 暫停抽卡" if self.game_model.running else "🎮 開始抽卡"
        keyboard = [
            [InlineKeyboardButton(toggle_text, callback_data="toggle_draw"), InlineKeyboardButton("📊 統計總覽", callback_data="check_overview")],
            [InlineKeyboardButton("⚙️ 設定門檻", callback_data="settings"), InlineKeyboardButton("🔄 刷新", callback_data="refresh")]
        ]
        web_ui = getattr(self.game_controller, 'web_ui', None)
        if web_ui:
            url_row = []
            url_row.append(InlineKeyboardButton("🏠 內網控制台", url=f"http://{web_ui.local_ip}:{web_ui.port}"))
            if web_ui.public_ip and web_ui.public_ip != "無法獲取":
                url_row.append(InlineKeyboardButton("🌍 外網控制台", url=f"http://{web_ui.public_ip}:{web_ui.port}"))
            keyboard.append(url_row)
        return InlineKeyboardMarkup(keyboard)

    def get_settings_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("5⭐ ➖", callback_data="set_5star_-1"), InlineKeyboardButton(f"5星: {self.game_model.min_5star}", callback_data="noop"), InlineKeyboardButton("5⭐ ➕", callback_data="set_5star_1")],
            [InlineKeyboardButton("4⭐ ➖", callback_data="set_4star_-1"), InlineKeyboardButton(f"4星: {self.game_model.min_4star}", callback_data="noop"), InlineKeyboardButton("4⭐ ➕", callback_data="set_4star_1")],
            [InlineKeyboardButton("🗑️ 重置數據", callback_data="reset_data")],
            [InlineKeyboardButton("🔙 返回主選單", callback_data="refresh")]
        ]
        return InlineKeyboardMarkup(keyboard)
        
    def get_success_keyboard(self):
        keyboard = [
            [InlineKeyboardButton("✅ 繼續抽卡", callback_data="continue_draw"), InlineKeyboardButton("🛑 停止抽卡", callback_data="stop_draw")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_overview_text(self):
        status = "🟢 運行中" if self.game_model.running else "🔴 已暫停"
        text = f"📊 **統計總覽**\n\n"
        text += f"🔹 **狀態：** {status}\n"
        text += f"🔹 **星級門檻：** 5星 {self.game_model.min_5star}個, 4星 {self.game_model.min_4star}個\n"
        text += f"🔹 **總抽卡次數：** {self.game_model.draw_count} 次\n"

        if self.game_model.draw_count > 0:
            stats = self.game_model.get_draw_statistics()
            text += f"🔹 **平均5星：** {stats['avg_5star']:.2f}/次\n"
            text += f"🔹 **平均4星：** {stats['avg_4star']:.2f}/次\n"
            text += f"🔹 **成功次數：** {stats['success_draws']} 次 (成功率: {stats['success_rate']:.1f}%)\n"

            dist = self.game_model.get_five_star_distribution()
            if dist:
                text += f"\n🌟 **五星分布：**\n"
                for stars, count in sorted(dist.items()):
                    text += f"  ⭐ {stars}個五星： {count} 次\n"

        text += f"\n🕐 {datetime.now().strftime('%H:%M:%S')}"
        return text

    def get_settings_text(self):
        text = f"⚙️ **門檻設定**\n\n"
        text += f"⭐ **5星門檻：** {self.game_model.min_5star} 個\n"
        text += f"⭐ **4星門檻：** {self.game_model.min_4star} 個\n\n"
        text += "使用 ➖ ➕ 按鈕調整門檻："
        return text

    # --- 訊息發送邏輯 ---
    async def _delete_last_notification(self):
        """刪除上一個互動對話框 (避免累積多個)"""
        if self.last_notification_message_id:
            try:
                await self.bot.delete_message(chat_id=self.chat_id, message_id=self.last_notification_message_id)
            except Exception:
                pass
            self.last_notification_message_id = None

    async def send_success_notification(self, screenshot, stars_5, stars_4, stars_3):
        """發送成功通知並附上截圖 (Async 內部方法)"""
        if not self.bot: return
        try:
            # 先刪除舊的互動對話框，避免越來越多
            await self._delete_last_notification()

            # 先發送截圖 (這樣圖片在上面)
            await self.send_screenshot_with_retry(screenshot, max_retries=3)

            # 再發送互動對話框 (確保在最底部)
            msg_text = (
                f"🎉 **達到星級門檻！**\n\n⭐ **結果：**\n• 5星：{stars_5} 個\n• 4星：{stars_4} 個\n• 3星：{stars_3} 個\n\n"
                f"🎯 **目標門檻：** 5星 {self.game_model.min_5star}個, 4星 {self.game_model.min_4star}個\n"
                f"📊 **總抽卡次數：** {self.game_model.draw_count} 次\n\n請確認是否要繼續抽卡："
            )
            
            message = await self.bot.send_message(chat_id=self.chat_id, text=msg_text, reply_markup=self.get_success_keyboard(), parse_mode='Markdown')
            self.last_notification_message_id = message.message_id
            
        except Exception as e:
            print(f"發送 Telegram 通知時發生錯誤: {e}")
            try:
                msg = await self.bot.send_message(chat_id=self.chat_id, text=f"🎉 達到目標！5星:{stars_5} 4星:{stars_4} 3星:{stars_3}", reply_markup=self.get_success_keyboard())
                self.last_notification_message_id = msg.message_id
            except: pass

    def screenshot_to_bytes(self, screenshot, quality=85, max_size=(1280, 720)):
        try:
            if screenshot is None: return None
            # OpenCV BGR -> RGB -> PIL
            pil_image = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB))
            
            if pil_image.size[0] > max_size[0] or pil_image.size[1] > max_size[1]:
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            bio = io.BytesIO()
            pil_image.save(bio, format='JPEG', quality=quality, optimize=True)
            bio.seek(0)
            return bio
        except Exception as e:
            print(f"轉換截圖錯誤: {e}")
            return None

    async def send_screenshot_with_retry(self, screenshot, max_retries=3):
        for attempt in range(max_retries):
            try:
                quality = 85 - (attempt * 15)
                max_size = (1280 - attempt * 200, 720 - attempt * 120)
                
                photo_bytes = self.screenshot_to_bytes(screenshot, quality=quality, max_size=max_size)
                if not photo_bytes: continue
                
                await asyncio.wait_for(
                    self.bot.send_photo(chat_id=self.chat_id, photo=photo_bytes, caption=f"📸 抽卡結果截圖 (品質: {quality}%)"),
                    timeout=15 + (attempt * 10)
                )
                return True
            except Exception as e:
                print(f"截圖發送失敗 (第 {attempt+1} 次): {e}")
                if attempt < max_retries - 1: await asyncio.sleep(2)
        return False

    async def send_message(self, text, keyboard=None):
        if not self.bot: return
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            print(f"發送訊息錯誤: {e}")

    # --- 關鍵修正：線程安全的同步調用 ---
    async def send_startup_menu(self):
        """啟動時發送互動主選單"""
        if not self.bot: return
        try:
            text = f"🚀 **無限抽自動化已啟動**\n\n{self.get_overview_text()}"
            await self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=self.get_main_keyboard(), parse_mode='Markdown')
        except Exception as e:
            print(f"發送啟動選單錯誤: {e}")

    def send_startup_menu_sync(self):
        """同步發送啟動互動選單 (Thread Safe)"""
        if not self.loop or not self.loop.is_running():
            return
        coro = self.send_startup_menu()
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def send_message_sync(self, text, keyboard=None):
        """同步發送訊息 (Thread Safe)"""
        if not self.loop or not self.loop.is_running():
            return
        coro = self.send_message(text, keyboard)
        asyncio.run_coroutine_threadsafe(coro, self.loop)
            
    def send_success_notification_sync(self, screenshot, stars_5, stars_4, stars_3):
        """同步發送成功通知 (Thread Safe)"""
        if not self.loop or not self.loop.is_running():
            print("Telegram Bot 未在運行中，略過通知")
            return
            
        coro = self.send_success_notification(screenshot, stars_5, stars_4, stars_3)
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        
        # 可選：在這裡可以捕捉 future 的異常，但不要阻塞主線程太久
        # try: future.result(timeout=0.1) except: pass