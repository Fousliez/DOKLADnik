from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .db import Database


def create_backup(db: Database, backup_root: Path, prefix: str = "manual") -> Path:
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = backup_root / f"{prefix}-{stamp}.zip"

    with tempfile.TemporaryDirectory(prefix="dokladnik-backup-") as tmp:
        tmp_path = Path(tmp)
        db_copy = tmp_path / "dokladnik.sqlite3"
        db.backup_to(db_copy)

        metadata = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": db.schema_version(),
            "database_name": db.path.name,
        }
        (tmp_path / "backup-info.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_copy, arcname="dokladnik.sqlite3")
            zf.write(tmp_path / "backup-info.json", arcname="backup-info.json")

    return target


def auto_backup_if_needed(db: Database, backup_root: Path) -> Path | None:
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if list(backup_root.glob(f"auto-{today}_*.zip")):
        return None

    target = create_backup(db, backup_root, prefix="auto")
    _prune_auto_backups(backup_root, keep=30)
    return target


def _prune_auto_backups(backup_root: Path, keep: int) -> None:
    files = sorted(
        backup_root.glob("auto-*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in files[keep:]:
        try:
            path.unlink()
        except OSError:
            pass
