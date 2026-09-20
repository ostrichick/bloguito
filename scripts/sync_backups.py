"""
Bloguito - Offsite Remote Backup Sync Tool
Downloads remote MariaDB/WordPress backups from Oracle Cloud to local PC safely.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SERVER_IP = "161.33.0.234"
USER = "ubuntu"
KEY_PATH = "C:/Users/gip4k/OneDrive/Documents/Oracle Cloud SSH/ssh-key-2026-09-08.key"
REMOTE_DIR = "/home/ubuntu/backups"
LOCAL_DIR = Path(__file__).resolve().parent.parent / "backups"


def main():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("🔄 Bloguito 오프사이트 백업 원격 동기화 시작")
    print("=" * 60)

    # 1. Fetch remote file list
    cmd = [
        "ssh", "-i", KEY_PATH,
        "-o", "StrictHostKeyChecking=no",
        f"{USER}@{SERVER_IP}",
        f"ls -1 {REMOTE_DIR}/*.gz 2>/dev/null || true"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ 원격 서버 연결 실패: {res.stderr.strip()}")
        sys.exit(1)

    remote_files = [line.strip() for line in res.stdout.splitlines() if line.strip().endswith(".gz")]
    if not remote_files:
        print("ℹ️ 원격 서버에 동기화할 백업 파일(.gz)이 없습니다.")
        return

    print(f"📦 원격 서버에서 {len(remote_files)}개의 백업 파일을 발견했습니다.\n")

    downloaded = 0
    for rf in remote_files:
        fname = Path(rf).name
        local_file = LOCAL_DIR / fname
        if local_file.exists():
            print(f"  ⏩ [이미 최신] {fname}")
        else:
            print(f"  ⬇️ [다운로드 중] {fname} ...")
            scp_cmd = [
                "scp", "-i", KEY_PATH,
                "-o", "StrictHostKeyChecking=no",
                f"{USER}@{SERVER_IP}:{rf}",
                str(local_file)
            ]
            sub = subprocess.run(scp_cmd, capture_output=True, text=True)
            if sub.returncode == 0 and local_file.exists():
                size_kb = round(local_file.stat().st_size / 1024, 1)
                print(f"  ✅ [완료] {fname} ({size_kb} KB)")
                downloaded += 1
            else:
                print(f"  ❌ [실패] {fname}: {sub.stderr.strip()}")

    print("\n" + "=" * 60)
    print(f"🎉 오프사이트 백업 동기화 완료! 신규 다운로드: {downloaded}개")
    print(f"📁 로컬 보관 위치: {LOCAL_DIR}")
    print("=" * 60)

    # List local backups
    local_backups = sorted(LOCAL_DIR.glob("*.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    print("\n[현재 로컬 백업 보관 목록]")
    print("-" * 75)
    print(f"{'파일명':<38} | {'크기(KB)':<10} | 최종 수정일시")
    print("-" * 75)
    for b in local_backups:
        dt = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = round(b.stat().st_size / 1024, 1)
        print(f"{b.name:<38} | {str(size_kb):<10} | {dt}")
    print("-" * 75)


if __name__ == "__main__":
    main()
