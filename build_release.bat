@echo off
chcp 65001 >nul
setlocal

:: =============================================
::  無限抽 - 打包發布資料夾
::  執行後會在同目錄產生 release_YYYYMMDD_HHMMSS\
:: =============================================

set "SRC=%~dp0"
set "TIMESTAMP=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "DEST=%SRC%release_%TIMESTAMP%"

echo.
echo 正在打包發布資料夾...
echo 目標: %DEST%
echo.

mkdir "%DEST%"
mkdir "%DEST%\mod"
mkdir "%DEST%\mouse\windows"
mkdir "%DEST%\mouse\emulator"
mkdir "%DEST%\templates"
mkdir "%DEST%\screenshots"
mkdir "%DEST%\logs"

:: --- 主程式與啟動器 ---
copy "%SRC%main.py"              "%DEST%\main.py"        >nul
copy "%SRC%Run.py"               "%DEST%\Run.py"         >nul
copy "%SRC%RUN.bat"              "%DEST%\RUN.bat"        >nul
copy "%SRC%kill_python.bat"      "%DEST%\kill_python.bat" >nul
copy "%SRC%requirements.txt"     "%DEST%\requirements.txt" >nul
copy "%SRC%README.md"            "%DEST%\README.md"      >nul

:: --- 設定檔範本（不含個人憑證）---
copy "%SRC%config.example.ini"   "%DEST%\config.example.ini" >nul

:: --- mod 模組（只複製 .py，排除 __pycache__）---
for %%f in ("%SRC%mod\*.py") do copy "%%f" "%DEST%\mod\" >nul

:: --- 圖片資源 ---
for %%f in ("%SRC%mouse\*.png") do copy "%%f" "%DEST%\mouse\" >nul
for %%f in ("%SRC%mouse\windows\*.png") do copy "%%f" "%DEST%\mouse\windows\" >nul
for %%f in ("%SRC%mouse\emulator\*.png") do copy "%%f" "%DEST%\mouse\emulator\" >nul

:: --- Web UI 模板（排除備份檔）---
copy "%SRC%templates\index.html" "%DEST%\templates\index.html" >nul

echo.
echo 打包完成！
echo.
echo 內容：
dir /b "%DEST%"
echo.
echo 請記得讓使用者將 config.example.ini 複製為 config.ini 並填入設定。
echo.
pause
