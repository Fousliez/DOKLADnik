from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from dokladnik.backup import auto_backup_if_needed
from dokladnik.db import Database
from dokladnik.paths import backup_dir, database_path
from dokladnik.repository import Repository
from dokladnik.ui.main_window import MainWindow
from dokladnik.ui.style import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DOKLADník")
    app.setOrganizationName("DOKLADnik")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    def exception_hook(exc_type, exc_value, exc_tb):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(details, file=sys.stderr)
        QMessageBox.critical(
            None,
            "DOKLADník – chyba",
            f"Došlo k neočekávané chybě:\n\n{exc_value}\n\n"
            "Podrobnosti byly vypsány do terminálu.",
        )

    sys.excepthook = exception_hook

    try:
        db = Database(database_path())
        db.initialize()
        if db.integrity_check() != "ok":
            raise RuntimeError("Kontrola SQLite databáze při spuštění neprošla.")
        auto_backup_if_needed(db, backup_dir())
        repo = Repository(db)
    except Exception as exc:
        QMessageBox.critical(None, "DOKLADník – databáze", str(exc))
        return 1

    window = MainWindow(repo, db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
