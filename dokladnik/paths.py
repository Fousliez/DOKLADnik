from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "DOKLADnik"


def data_dir() -> Path:
    override = os.environ.get("DOKLADNIK_DATA_DIR")
    if override:
        root = Path(override).expanduser().resolve()
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        root = Path(xdg).expanduser() / APP_DIR_NAME if xdg else Path.home() / ".local" / "share" / APP_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "dokladnik.sqlite3"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path
