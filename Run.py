import sys
import os
import ctypes
import subprocess
import shutil
import re
import traceback  # 新增：用於捕捉詳細錯誤
import time       # 新增：用於產生時間戳記

# 定義需要檢查的關鍵模組 (對應 requirements.txt)
REQUIRED_MODULES = [
    "cv2",          # opencv-python
    "mss",          # mss
    "fastapi",      # fastapi
    "uvicorn",      # uvicorn
    "telegram",     # python-telegram-bot
    "PIL",          # pillow
    "numpy"         # numpy
]

def write_error_log(error_msg):
    """將錯誤訊息寫入 logs 資料夾"""
    try:
        # 確保工作目錄正確
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(base_dir, 'logs')
        
        # 如果 logs 資料夾不存在則建立
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 建立帶有時間戳記的檔名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f'launcher_error_{timestamp}.log')
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"記錄時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n")
            f.write(error_msg)
            f.write("\n" + "=" * 60 + "\n")
            
        print(f"\n[系統] 詳細錯誤報告已儲存至: {log_file}")
    except Exception as e:
        print(f"\n[警告] 無法寫入錯誤日誌: {e}")

def is_admin():
    """檢查是否具有管理員權限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def run_as_admin():
    """重新以管理員身分啟動自身"""
    script = os.path.abspath(__file__)
    params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    except Exception as e:
        err_msg = f"[錯誤] 無法獲取管理員權限: {e}"
        print(err_msg)
        write_error_log(err_msg)
        input("按 Enter 鍵退出...")
        sys.exit(1)

def find_python_versions():
    """
    偵測系統中可用的 Python 版本
    回傳列表: [{'version': '3.10', 'path': 'C:\\...\\python.exe', 'arch': '64bit'}, ...]
    """
    versions = []
    
    # 1. 嘗試使用 Windows 的 'py' 啟動器偵測
    try:
        output = subprocess.check_output(["py", "--list-paths"], stderr=subprocess.STDOUT).decode("utf-8", errors="ignore")
        for line in output.splitlines():
            match = re.search(r'-(\d+\.\d+)(?:-(\d+))?\s+(.+)', line)
            if match:
                ver, arch, path = match.groups()
                versions.append({
                    'version': ver,
                    'arch': f"{arch}bit" if arch else "32bit",
                    'path': path.strip(),
                    'source': 'py launcher'
                })
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # 2. 加入當前執行的 Python
    current_path = sys.executable
    if not any(os.path.normcase(v['path']) == os.path.normcase(current_path) for v in versions):
        ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        versions.append({
            'version': ver,
            'arch': 'Unknown',
            'path': current_path,
            'source': 'current'
        })

    return versions

def select_python_version(versions):
    """讓使用者選擇 Python 版本"""
    if not versions:
        print("[錯誤] 找不到任何 Python 環境！")
        return sys.executable

    if len(versions) == 1:
        print(f"偵測到單一 Python 環境: {versions[0]['version']} ({versions[0]['path']})")
        return versions[0]['path']

    print("\n🔍 偵測到多個 Python 版本，請選擇要執行的環境：")
    print("-" * 60)
    print(f"{'編號':<5} {'版本':<10} {'架構':<8} {'路徑'}")
    print("-" * 60)
    
    for i, v in enumerate(versions):
        print(f"{i+1:<5} {v['version']:<10} {v['arch']:<8} {v['path']}")
    
    print("-" * 60)
    
    while True:
        choice = input(f"請輸入編號 (1-{len(versions)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(versions):
            selected = versions[int(choice)-1]
            print(f"已選擇: Python {selected['version']} ({selected['path']})")
            return selected['path']
        print("輸入無效，請重新輸入。")

def check_dependencies(python_path):
    """檢查選定的 Python 是否擁有必要模組"""
    print("\n🔍 正在檢查相依套件...")
    
    imports = "; ".join([f"import {m}" for m in REQUIRED_MODULES])
    cmd = [python_path, "-c", imports]
    
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ 所有相依套件檢查通過。")
        return True
    except subprocess.CalledProcessError:
        print("❌ 發現缺少必要的 Python 套件。")
        return False

def install_dependencies(python_path):
    """自動安裝 requirements.txt"""
    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        print(f"[錯誤] 找不到 {req_file}，無法自動安裝。")
        return False

    print(f"\n⚙️ 準備自動執行 pip install...")
    confirm = input("是否立即安裝/修復套件？(Y/n): ").strip().lower()
    
    if confirm != '' and confirm != 'y':
        print("使用者取消安裝。程式可能會因為缺少套件而崩潰。")
        return False

    try:
        print("-" * 50)
        subprocess.check_call([python_path, "-m", "pip", "install", "-r", req_file])
        print("-" * 50)
        print("✅ 套件安裝/更新完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[錯誤] 安裝過程發生錯誤: {e}")
        return False

def main():
    # 1. 切換工作目錄
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 2. 檢查權限
    if not is_admin():
        print("正在請求系統管理員權限...")
        run_as_admin()
        return

    print("="*60)
    print("   無限抽自動化啟動器 (Launcher)   ")
    print("="*60)

    # 3. 偵測並選擇 Python
    versions = find_python_versions()
    target_python = select_python_version(versions)

    # 4. 檢查依賴並自動修復
    if not check_dependencies(target_python):
        if install_dependencies(target_python):
            if not check_dependencies(target_python):
                print("[警告] 套件似乎仍未安裝完整，將嘗試強制啟動...")
        else:
            print("[警告] 跳過安裝，將嘗試強制啟動...")

    # 5. 啟動主程式
    print("\n🚀 正在啟動 main.py ...")
    print("-" * 60)
    
    # 執行主程式
    return_code = subprocess.call([target_python, "main.py"])
    
    # 檢查主程式回傳值，如果不為 0 代表異常退出
    if return_code != 0:
        raise Exception(f"主程式異常退出 (Exit Code: {return_code})")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程式已手動停止。")
    except Exception:
        # [全域錯誤攔截] 
        # 無論哪裡發生錯誤，都會被這裡捕捉，並寫入 Log
        error_msg = traceback.format_exc()
        print("\n" + "!"*60)
        print("   啟動器發生嚴重錯誤，程式即將關閉")
        print("!"*60 + "\n")
        print(error_msg)
        
        # 寫入檔案
        write_error_log(error_msg)
        
        # 強制暫停，確保視窗不會消失
        input("\n請按 Enter 鍵關閉視窗...")