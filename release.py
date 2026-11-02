"""
Phát hành bản mới của Bot lên GitHub để tất cả các máy khác tự động tải bản mới về.

Cách dùng:
    python release.py 1.0.1 "Ghi chú cập nhật"
    (Hoặc chỉ cần chạy build_release.bat)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, "version.py")
EXE = os.path.join(HERE, "dist", "market_bot.exe")
LOCAL_EXE = os.path.join(HERE, "market_bot.exe")

def read_version_file():
    with open(VERSION_FILE, encoding="utf-8") as f:
        return f.read()

def parse(v):
    return tuple(int(x) for x in v.split("."))

def run(cmd):
    print("  >", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    return subprocess.run(cmd, cwd=HERE).returncode == 0

def auto_increment_version(cur):
    parts = [int(x) for x in cur.split(".")]
    parts[-1] += 1
    return ".".join(str(x) for x in parts)

def main():
    original = read_version_file()
    cur_ver = re.search(r'VERSION = "([\d.]+)"', original).group(1)
    repo = re.search(r'UPDATE_REPO = "([^"]+)"', original).group(1)

    if len(sys.argv) > 1 and re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        new_ver = sys.argv[1]
    else:
        new_ver = auto_increment_version(cur_ver)
        print(f"[*] Tự động tăng phiên bản: {cur_ver} -> {new_ver}")

    notes = sys.argv[2] if len(sys.argv) > 2 else f"Queen Market Bot v{new_ver}"

    if parse(new_ver) <= parse(cur_ver):
        print(f"[!] Phiên bản mới ({new_ver}) phải lớn hơn bản hiện tại ({cur_ver}).")
        sys.exit(1)

    if not shutil.which("gh"):
        print("[!] Chưa cài GitHub CLI (gh). Tải tại https://cli.github.com rồi chạy: gh auth login")
        sys.exit(1)

    print(f"\n[1/4] Cập nhật phiên bản {cur_ver} -> {new_ver} trong version.py...")
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(original.replace(f'VERSION = "{cur_ver}"', f'VERSION = "{new_ver}"'))

    print("\n[2/4] Đang đóng gói PyInstaller -> market_bot.exe...")
    work = os.path.join(tempfile.gettempdir(), "marketbot-build")
    ok = run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", "market_bot",
        "--collect-submodules", "websocket",
        "--collect-submodules", "discord",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", work,
        "--specpath", work,
        os.path.join(HERE, "bot.py")
    ])

    if not ok or not os.path.exists(EXE):
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(original)
        print("\n[!] Build exe thất bại. Đã khôi phục version.py.")
        sys.exit(1)

    # Copy ra thư mục gốc
    try:
        shutil.copy2(EXE, LOCAL_EXE)
    except Exception:
        pass

    print(f"\n[3/4] Đang đăng bản v{new_ver} lên GitHub Releases (github.com/{repo}/releases)...")
    ok = run([
        "gh", "release", "create", f"v{new_ver}", EXE,
        "--repo", repo,
        "--title", f"Queen Market Bot v{new_ver}",
        "--notes", notes
    ])

    if not ok:
        print("\n[!] Lỗi tải lên GitHub Releases.")
        print(f"    Thử lại bằng lệnh:")
        print(f'    gh release create v{new_ver} "{EXE}" --repo {repo} --title "Queen Market Bot v{new_ver}" --notes "{notes}"')
        sys.exit(1)

    print("\n" + "=" * 65)
    print(f"🎉 PHÁT HÀNH BẢN v{new_ver} THÀNH CÔNG LÊN GITHUB RELEASES!")
    print(f"• File exe tại: {LOCAL_EXE}")
    print(f"• Link tải: https://github.com/{repo}/releases/tag/v{new_ver}")
    print("• Cơ chế Auto-Update: Bất kỳ ai đang bật bản cũ, chỉ cần mở lại")
    print(f"  market_bot.exe là máy họ sẽ TỰ ĐỘNG TẢI BẢN v{new_ver} NÀY VỀ!")
    print("=" * 65)

if __name__ == "__main__":
    main()
