#!/usr/bin/env python3
"""SQLite 会话库与上传文件备份/恢复工具。"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DB = DATA_DIR / "sessions" / "sessions.db"
UPLOADS_DIR = DATA_DIR / "uploads"
BACKUP_DIR = PROJECT_ROOT / "backups"


def backup(target_dir: Path = BACKUP_DIR) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = target_dir / f"backup-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    if SESSIONS_DB.exists():
        # 使用 SQLite 在线备份 API，避免直接复制时遇到写入中的 DB。
        with sqlite3.connect(SESSIONS_DB) as source, sqlite3.connect(out_dir / "sessions.db") as dest:
            source.backup(dest)
    else:
        print(f"[WARN] 会话数据库不存在: {SESSIONS_DB}")

    if UPLOADS_DIR.exists():
        shutil.copytree(UPLOADS_DIR, out_dir / "uploads", dirs_exist_ok=True)
    else:
        (out_dir / "uploads").mkdir(parents=True, exist_ok=True)

    print(f"[OK] 备份完成: {out_dir}")
    return out_dir


def restore(source_dir: Path, force: bool = False) -> None:
    if not source_dir.exists():
        raise FileNotFoundError(f"备份目录不存在: {source_dir}")
    db_file = source_dir / "sessions.db"
    uploads = source_dir / "uploads"
    if not db_file.exists():
        raise FileNotFoundError(f"备份中缺少 sessions.db: {db_file}")

    if not force:
        raise RuntimeError("恢复会覆盖当前 data/sessions/sessions.db 与 data/uploads；确认后添加 --force")

    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_file, SESSIONS_DB)
    if uploads.exists():
        if UPLOADS_DIR.exists():
            shutil.rmtree(UPLOADS_DIR)
        shutil.copytree(uploads, UPLOADS_DIR)
    print(f"[OK] 恢复完成: {source_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="备份或恢复 VLM Chat Assistant 数据")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="备份 SQLite 会话库和上传文件")
    b.add_argument("--target-dir", type=Path, default=BACKUP_DIR, help="备份输出目录")

    r = sub.add_parser("restore", help="从备份恢复数据")
    r.add_argument("source_dir", type=Path, help="备份目录，例如 backups/backup-20260613-120000")
    r.add_argument("--force", action="store_true", help="确认覆盖当前数据")

    args = parser.parse_args(argv)
    if args.command == "backup":
        backup(args.target_dir)
        return 0
    if args.command == "restore":
        restore(args.source_dir, args.force)
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
