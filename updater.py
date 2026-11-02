"""
Tự động cập nhật bot từ GitHub Releases.
Luồng: Hỏi API bản mới nhất -> so phiên bản -> tải market_bot.exe về .new
-> kiểm tra (MZ, kích thước, sha256) -> đổi tên exe đang chạy thành .old
-> đặt bản mới vào vị trí cũ -> khởi động lại bản mới.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

from version import UPDATE_REPO, VERSION, ASSET_NAME

API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
HEADERS = {"User-Agent": "queen-market-bot-updater", "Accept": "application/vnd.github+json"}

def parse_version(v):
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple((parts + [0, 0, 0])[:3])

def is_frozen():
    return getattr(sys, "frozen", False)

def exe_path():
    return os.path.abspath(sys.executable)

def get_base_dir():
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def cleanup_old():
    """Xóa các file .old còn lại từ lần cập nhật trước."""
    if not is_frozen():
        return
    for _ in range(10):
        leftovers = glob.glob(glob.escape(exe_path()) + "*.old") + glob.glob(glob.escape(exe_path()) + ".new")
        if not leftovers:
            return
        for f in leftovers:
            try:
                os.remove(f)
            except OSError:
                pass
        time.sleep(0.2)

def check_update():
    """Kiểm tra xem có bản mới trên GitHub không. Trả về dict thông tin nếu có bản mới."""
    try:
        req = urllib.request.Request(API_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        latest = data.get("tag_name") or ""
        if parse_version(latest) <= parse_version(VERSION):
            return None

        for asset in data.get("assets", []):
            if asset.get("name", "").lower() == ASSET_NAME.lower():
                digest = asset.get("digest") or ""
                return {
                    "version": latest.lstrip("vV"),
                    "url": asset["browser_download_url"],
                    "size": int(asset.get("size") or 0),
                    "sha256": digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None,
                }
    except Exception:
        pass
    return None

def download_update(info):
    """Tải bản mới về file .new với thanh tiến trình."""
    dest = exe_path() + ".new"
    req = urllib.request.Request(info["url"], headers={"User-Agent": HEADERS["User-Agent"]})
    sha = hashlib.sha256()
    done = 0

    print(f"\n[*] Đang tải bản cập nhật v{info['version']}...")
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or info["size"] or 0)
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)

            # Vẽ thanh tiến trình
            pct = (done / total * 100) if total > 0 else 0
            mb_done = done / (1024 * 1024)
            mb_total = total / (1024 * 1024) if total > 0 else 0
            bar_len = 25
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            sys.stdout.write(f"\r  [{bar}] {pct:.1f}% ({mb_done:.1f}/{mb_total:.1f} MB)")
            sys.stdout.flush()

    print()
    with open(dest, "rb") as f:
        is_exe = f.read(2) == b"MZ"
    bad_size = info["size"] and done != info["size"]
    bad_hash = info["sha256"] and sha.hexdigest() != info["sha256"]

    if not is_exe or bad_size or bad_hash:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise ValueError("File tải về bị lỗi hoặc không đầy đủ.")
    return dest

def install_and_restart(new_file):
    """Thay thế exe đang chạy bằng bản mới và khởi động lại."""
    exe = exe_path()
    old = f"{exe}.{int(time.time())}.old"
    os.replace(exe, old)
    try:
        os.replace(new_file, exe)
    except OSError:
        os.replace(old, exe)
        raise

    print("[+] Cài đặt thành công! Đang khởi động lại bản mới...")
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen([exe] + sys.argv[1:], cwd=os.path.dirname(exe), env=env)
    sys.exit(0)

def auto_update_check():
    """Hàm chính gọi khi khởi động bot."""
    cleanup_old()
    if not is_frozen():
        return False

    print(f"[*] Phiên bản hiện tại: v{VERSION}")
    print("[*] Đang kiểm tra cập nhật từ GitHub...")
    info = check_update()
    if not info:
        print("[+] Bạn đang dùng phiên bản mới nhất!")
        return False

    print(f"\n============================================================")
    print(f"🚀 PHÁT HIỆN BẢN MỚI: v{info['version']} (Hiện tại: v{VERSION})")
    print(f"============================================================")
    try:
        new_file = download_update(info)
        install_and_restart(new_file)
        return True
    except Exception as e:
        print(f"[!] Cập nhật thất bại: {e}")
        print("[*] Sẽ tiếp tục chạy bản hiện tại...")
        return False
