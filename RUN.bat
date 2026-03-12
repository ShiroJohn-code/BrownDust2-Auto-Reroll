@echo off
REM ----- 檢查是否有管理員權限 -----
:: 使用 net session 檢查（通常可用），若失敗則非管理員
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要系統管理員權限，嘗試以提升權限重新啟動...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM ----- 已是管理員，切換到腳本目錄並執行 python -----
cd /d "%~dp0"
REM 若要指定完整 python 路徑可改為 "C:\Python39\python.exe"
python "%~dp0main.py" %*
pause
