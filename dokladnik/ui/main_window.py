from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from ..backup import create_backup
from ..paths import backup_dir
from .views import (
    ClientsWidget,
    DashboardWidget,
    InvoicesWidget,
    JobsWidget,
    SettingsWidget,
    StatsWidget,
)


class MainWindow(QMainWindow):
    def __init__(self, repo, db):
        super().__init__()
        self.repo = repo
        self.db = db
        self.setWindowTitle("DOKLADník")
        self.resize(1500, 900)
        self.setMinimumSize(1050, 650)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = DashboardWidget(repo)
        self.jobs = JobsWidget(repo)
        self.clients = ClientsWidget(repo)
        self.invoices = InvoicesWidget(repo)
        self.stats = StatsWidget(repo)
        self.settings = SettingsWidget(repo, db)

        self.tabs.addTab(self.dashboard, "Přehled")
        self.tabs.addTab(self.jobs, "Zakázky")
        self.tabs.addTab(self.clients, "Klienti")
        self.tabs.addTab(self.invoices, "Faktury")
        self.tabs.addTab(self.stats, "Statistiky")
        self.tabs.addTab(self.settings, "Nastavení")

        self.jobs.data_changed.connect(self._data_changed)
        self.clients.data_changed.connect(self._data_changed)
        self.invoices.data_changed.connect(self._data_changed)
        self.settings.data_changed.connect(self._data_changed)
        self.tabs.currentChanged.connect(self._refresh_current_tab)

        self._build_menu()
        self._build_shortcuts()
        self._update_status()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Soubor")

        backup_action = QAction("Vytvořit zálohu", self)
        backup_action.setShortcut(QKeySequence("Ctrl+B"))
        backup_action.triggered.connect(self.create_backup)
        file_menu.addAction(backup_action)

        file_menu.addSeparator()
        exit_action = QAction("Konec", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools = self.menuBar().addMenu("Nástroje")
        integrity = QAction("Kontrola databáze", self)
        integrity.triggered.connect(self.check_integrity)
        tools.addAction(integrity)

        refresh = QAction("Obnovit vše", self)
        refresh.setShortcut(QKeySequence("Ctrl+Shift+R"))
        refresh.triggered.connect(self.refresh_all)
        tools.addAction(refresh)

    def _build_shortcuts(self) -> None:
        shortcut = QShortcut(QKeySequence("Ctrl+1"), self)
        shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(0))
        shortcut = QShortcut(QKeySequence("Ctrl+2"), self)
        shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(1))
        shortcut = QShortcut(QKeySequence("Ctrl+3"), self)
        shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(2))
        shortcut = QShortcut(QKeySequence("Ctrl+4"), self)
        shortcut.activated.connect(lambda: self.tabs.setCurrentIndex(3))

    def _data_changed(self) -> None:
        self.dashboard.refresh()
        self.stats.refresh()
        self._update_status()

    def _refresh_current_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()
        self._update_status()

    def refresh_all(self) -> None:
        for widget in (
            self.dashboard, self.jobs, self.clients,
            self.invoices, self.stats, self.settings,
        ):
            refresh = getattr(widget, "refresh", None)
            if callable(refresh):
                refresh()
        self._update_status()

    def _update_status(self) -> None:
        stats = self.repo.dashboard()
        self.statusBar().showMessage(
            f"DB: {self.db.path}   |   Zakázky: {stats['job_count']}   |   "
            f"Faktury: {stats['invoice_count']}   |   Schema: {self.db.schema_version()}"
        )

    def create_backup(self) -> None:
        try:
            target = create_backup(self.db, backup_dir(), prefix="manual")
            QMessageBox.information(self, "Záloha", f"Záloha vytvořena:\n{target}")
        except Exception as exc:
            QMessageBox.critical(self, "Záloha", str(exc))

    def check_integrity(self) -> None:
        try:
            result = self.db.integrity_check()
        except Exception as exc:
            QMessageBox.critical(self, "Databáze", str(exc))
            return
        if result == "ok":
            QMessageBox.information(self, "Databáze", "Kontrola databáze: OK")
        else:
            QMessageBox.warning(self, "Databáze", f"Výsledek kontroly: {result}")
