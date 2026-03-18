"""
GitHub 自動更新模組
==================
在專案啟動時自動檢查 GitHub Releases，若有新版本則下載並更新。

使用方式：
1. 將此檔案放入你的專案根目錄
2. 在你的主程式 (main.py) 開頭加入：
       from auto_updater import check_and_update
       check_and_update()
3. 在 GitHub 上建立 Release，並上傳打包好的 .zip 檔案

打包方式（上傳到 GitHub Release 的 .zip）：
    把你的專案檔案打包成 .zip，例如：
    zip -r my_project_v1.1.0.zip *.py config/ utils/ ...
"""

import json
import os
import sys
import shutil
import zipfile
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
# ★ 請修改以下設定 ★
# ============================================================
GITHUB_OWNER = "你的GitHub帳號"       # 例如 "octocat"
GITHUB_REPO = "你的Repo名稱"          # 例如 "my-project"
CURRENT_VERSION = "1.0.0"             # 目前版本號（語意化版本）
# ============================================================

# GitHub API 網址
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# 更新暫存資料夾
UPDATE_TEMP_DIR = Path("_update_temp")

# 版本紀錄檔（可選，用來追蹤本地版本）
VERSION_FILE = Path("VERSION")


def parse_version(version_str: str) -> tuple:
    """將版本字串轉換為可比較的 tuple，例如 '1.2.3' -> (1, 2, 3)"""
    clean = version_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def get_local_version() -> str:
    """取得本地版本號"""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return CURRENT_VERSION


def save_local_version(version: str):
    """儲存版本號到本地"""
    VERSION_FILE.write_text(version.lstrip("vV"))


def fetch_latest_release() -> dict | None:
    """從 GitHub API 取得最新 Release 資訊"""
    try:
        req = urllib.request.Request(API_URL)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", f"{GITHUB_REPO}-updater")

        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[更新] 尚未建立任何 Release，跳過更新檢查。")
        else:
            print(f"[更新] GitHub API 錯誤：{e.code} {e.reason}")
        return None
    except urllib.error.URLError:
        print("[更新] 無法連線到 GitHub，跳過更新檢查。")
        return None
    except Exception as e:
        print(f"[更新] 檢查更新時發生錯誤：{e}")
        return None


def find_zip_asset(release: dict) -> dict | None:
    """從 Release 中找到 .zip 附件"""
    for asset in release.get("assets", []):
        if asset["name"].endswith(".zip"):
            return asset
    return None


def download_file(url: str, dest: Path):
    """下載檔案"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", f"{GITHUB_REPO}-updater")
    req.add_header("Accept", "application/octet-stream")

    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        block_size = 8192

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    print(f"\r[更新] 下載中... {pct:.1f}%", end="", flush=True)

    if total > 0:
        print()  # 換行


def apply_update(zip_path: Path, project_dir: Path):
    """
    解壓縮並覆蓋專案檔案。
    會保留不在 zip 中的本地檔案（例如設定檔、資料庫等）。
    """
    extract_dir = UPDATE_TEMP_DIR / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # 處理 zip 內可能有一層根資料夾的情況
    contents = list(extract_dir.iterdir())
    if len(contents) == 1 and contents[0].is_dir():
        source_dir = contents[0]
    else:
        source_dir = extract_dir

    # 複製檔案到專案目錄
    updated_files = []
    for item in source_dir.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(source_dir)
            dest = project_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            updated_files.append(str(rel_path))

    return updated_files


def cleanup():
    """清理暫存資料夾"""
    if UPDATE_TEMP_DIR.exists():
        shutil.rmtree(UPDATE_TEMP_DIR, ignore_errors=True)


def check_and_update(
    auto_restart: bool = True,
    skip_confirm: bool = False,
) -> bool:
    """
    主要函式：檢查並執行更新。

    參數：
        auto_restart: 更新後是否自動重啟程式
        skip_confirm: 是否跳過使用者確認（True = 靜默更新）

    回傳：
        True 表示有更新並已套用，False 表示無需更新
    """
    print("[更新] 正在檢查最新版本...")

    local_ver = get_local_version()
    release = fetch_latest_release()
    if release is None:
        return False

    remote_ver = release.get("tag_name", "0.0.0")
    release_name = release.get("name", remote_ver)

    local_tuple = parse_version(local_ver)
    remote_tuple = parse_version(remote_ver)

    if remote_tuple <= local_tuple:
        print(f"[更新] 已是最新版本 (v{local_ver})。")
        return False

    print(f"[更新] 發現新版本！ v{local_ver} → {remote_ver}")
    print(f"[更新] 更新內容：{release_name}")

    # 顯示 Release Notes（如果有的話）
    body = release.get("body", "").strip()
    if body:
        print(f"[更新] 更新說明：\n{body}\n")

    # 使用者確認
    if not skip_confirm:
        answer = input("[更新] 是否要更新？(Y/n): ").strip().lower()
        if answer in ("n", "no"):
            print("[更新] 已取消更新。")
            return False

    # 找到 .zip 附件
    asset = find_zip_asset(release)
    if asset is None:
        print("[更新] Release 中找不到 .zip 檔案，無法更新。")
        print("[更新] 請確認 Release 中有上傳 .zip 附件。")
        return False

    try:
        # 建立暫存資料夾
        UPDATE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = UPDATE_TEMP_DIR / asset["name"]

        # 下載
        print(f"[更新] 正在下載 {asset['name']}...")
        download_file(asset["browser_download_url"], zip_path)

        # 套用更新
        project_dir = Path(__file__).parent.resolve()
        print("[更新] 正在套用更新...")
        updated_files = apply_update(zip_path, project_dir)

        # 儲存新版本號
        save_local_version(remote_ver)

        print(f"[更新] 更新完成！已更新 {len(updated_files)} 個檔案。")
        for f in updated_files[:10]:
            print(f"  ✓ {f}")
        if len(updated_files) > 10:
            print(f"  ... 還有 {len(updated_files) - 10} 個檔案")

    except Exception as e:
        print(f"[更新] 更新過程中發生錯誤：{e}")
        return False
    finally:
        cleanup()

    # 自動重啟
    if auto_restart:
        print("[更新] 正在重新啟動程式...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    return True


# ============================================================
# 直接執行此檔案可以手動觸發更新檢查
# ============================================================
if __name__ == "__main__":
    check_and_update()
