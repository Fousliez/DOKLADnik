from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..backup import create_backup
from ..invoice_pdf import generate_invoice_pdf
from ..paths import backup_dir, export_dir
from .common import (
    ACTIVITY_LABELS,
    DOCUMENT_LABELS,
    PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS,
    cents_to_text,
)
from .dialogs import ClientDialog, InvoiceDialog, JobDialog
from .table_model import Column, DictTableModel


RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _activity(value, _row) -> str:
    return ACTIVITY_LABELS.get(value, str(value or ""))


def _money(value, _row) -> str:
    return cents_to_text(value)


def _payment_method(value, _row) -> str:
    return PAYMENT_METHOD_LABELS.get(value, str(value or ""))


def _payment_status(value, _row) -> str:
    return PAYMENT_STATUS_LABELS.get(value, str(value or ""))


def _document(value, row) -> str:
    if value == "INVOICE" and row.get("invoice_number"):
        return f"Faktura {row['invoice_number']}"
    return DOCUMENT_LABELS.get(value, str(value or ""))


def _setup_table(table: QTableView, model: DictTableModel) -> None:
    table.setModel(model)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)


class DashboardWidget(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo

        outer = QVBoxLayout(self)
        filters = QHBoxLayout()

        self.activity = QComboBox()
        for code in ("ALL", "DDD", "DOCISTA"):
            self.activity.addItem(ACTIVITY_LABELS[code], code)

        self.period = QComboBox()
        self.period.addItem("Všechny roky", "ALL")
        self.period.addItem("Rok", "YEAR")
        self.period.addItem("Měsíc", "MONTH")
        self.period.addItem("Vlastní období", "CUSTOM")
        self.period.setCurrentIndex(self.period.findData("YEAR"))

        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(date.today().year)

        self.month = QComboBox()
        month_names = [
            "leden", "únor", "březen", "duben", "květen", "červen",
            "červenec", "srpen", "září", "říjen", "listopad", "prosinec",
        ]
        for num, name in enumerate(month_names, 1):
            self.month.addItem(name, num)
        self.month.setCurrentIndex(date.today().month - 1)

        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd.MM.yyyy")

        filters.addWidget(QLabel("Činnost:"))
        filters.addWidget(self.activity)
        filters.addSpacing(12)
        filters.addWidget(QLabel("Období:"))
        filters.addWidget(self.period)
        filters.addWidget(self.year)
        filters.addWidget(self.month)
        filters.addWidget(self.date_from)
        filters.addWidget(QLabel("až"))
        filters.addWidget(self.date_to)
        filters.addStretch(1)
        outer.addLayout(filters)

        cards = QGridLayout()
        self.card_labels: dict[str, QLabel] = {}
        definitions = [
            ("revenue_cents", "Tržby"),
            ("tips_cents", "Dýška"),
            ("travel_cents", "Cestovné"),
            ("total_cents", "Celkem"),
            ("job_count", "Zakázky"),
            ("average_cents", "Průměr"),
            ("unpaid_cents", "Nezaplaceno"),
            ("invoice_count", "Faktury"),
        ]
        for i, (key, title) in enumerate(definitions):
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            label = QLabel("0")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 22px; font-weight: 700;")
            box_layout.addWidget(label)
            self.card_labels[key] = label
            cards.addWidget(box, i // 4, i % 4)
        outer.addLayout(cards)

        bottom = QHBoxLayout()

        pay_group = QGroupBox("Podle způsobu platby")
        pay_layout = QVBoxLayout(pay_group)
        self.pay_table = QTableWidget(0, 3)
        self.pay_table.setHorizontalHeaderLabels(["Platba", "Zakázky", "Celkem"])
        self.pay_table.horizontalHeader().setStretchLastSection(True)
        self.pay_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pay_layout.addWidget(self.pay_table)
        bottom.addWidget(pay_group, 1)

        source_group = QGroupBox("Podle zdroje zákazníka")
        source_layout = QVBoxLayout(source_group)
        self.source_table = QTableWidget(0, 3)
        self.source_table.setHorizontalHeaderLabels(["Zdroj", "Zakázky", "Celkem"])
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        source_layout.addWidget(self.source_table)
        bottom.addWidget(source_group, 1)

        outer.addLayout(bottom, 1)

        for widget in (
            self.activity, self.period, self.year, self.month,
            self.date_from, self.date_to,
        ):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._filter_changed)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._filter_changed)
            else:
                widget.dateChanged.connect(self._filter_changed)

        self._filter_changed()

    def _filter_changed(self, *_args) -> None:
        mode = self.period.currentData()
        self.year.setVisible(mode in {"YEAR", "MONTH"})
        self.month.setVisible(mode == "MONTH")
        custom = mode == "CUSTOM"
        self.date_from.setVisible(custom)
        self.date_to.setVisible(custom)
        self.refresh()

    def _bounds(self) -> tuple[str | None, str | None]:
        mode = self.period.currentData()
        if mode == "ALL":
            return None, None
        if mode == "YEAR":
            y = self.year.value()
            return f"{y}-01-01", f"{y}-12-31"
        if mode == "MONTH":
            y = self.year.value()
            m = int(self.month.currentData())
            last = calendar.monthrange(y, m)[1]
            return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last:02d}"
        return (
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
        )

    def refresh(self) -> None:
        from_date, to_date = self._bounds()
        activity = self.activity.currentData()
        stats = self.repo.dashboard(activity, from_date, to_date)
        money_keys = {
            "revenue_cents", "tips_cents", "travel_cents",
            "total_cents", "average_cents", "unpaid_cents",
        }
        for key, label in self.card_labels.items():
            value = stats.get(key, 0)
            label.setText(cents_to_text(value) if key in money_keys else f"{int(value):,}".replace(",", " "))

        payments = self.repo.payment_breakdown(activity, from_date, to_date)
        self.pay_table.setRowCount(len(payments))
        for row, item in enumerate(payments):
            values = [
                PAYMENT_METHOD_LABELS.get(item["payment_method"], item["payment_method"]),
                str(item["job_count"]),
                cents_to_text(item["total_cents"]),
            ]
            for col, value in enumerate(values):
                self.pay_table.setItem(row, col, QTableWidgetItem(value))

        sources = self.repo.source_breakdown(activity, from_date, to_date)
        self.source_table.setRowCount(len(sources))
        for row, item in enumerate(sources):
            values = [item["source_name"], str(item["job_count"]), cents_to_text(item["total_cents"])]
            for col, value in enumerate(values):
                self.source_table.setItem(row, col, QTableWidgetItem(value))


class JobsWidget(QWidget):
    data_changed = Signal()

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        outer = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.add_btn = QPushButton("+ Nová zakázka")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        self.invoice_btn = QPushButton("Faktura")
        self.refresh_btn = QPushButton("Obnovit")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hledat jméno, adresu, telefon, službu, fakturu…")
        self.activity = QComboBox()
        for code in ("ALL", "DDD", "DOCISTA"):
            self.activity.addItem(ACTIVITY_LABELS[code], code)

        for w in (self.add_btn, self.edit_btn, self.delete_btn, self.invoice_btn, self.refresh_btn):
            bar.addWidget(w)
        bar.addSpacing(10)
        bar.addWidget(QLabel("Činnost:"))
        bar.addWidget(self.activity)
        bar.addWidget(self.search, 1)
        outer.addLayout(bar)

        self.model = DictTableModel(
            [
                Column("job_date", "Datum"),
                Column("activity", "Činnost", _activity),
                Column("customer_name", "Klient"),
                Column("service_address", "Adresa"),
                Column("service_summary", "Co se dělalo"),
                Column("price_cents", "Cena", _money, RIGHT),
                Column("tip_cents", "Dýško", _money, RIGHT),
                Column("travel_cents", "Cesta", _money, RIGHT),
                Column("total_cents", "Celkem", _money, RIGHT),
                Column("payment_method", "Platba", _payment_method),
                Column("payment_status", "Zaplacení", _payment_status),
                Column("document_type", "Doklad", _document),
                Column("source", "Zdroj"),
            ]
        )
        self.table = QTableView()
        _setup_table(self.table, self.model)
        outer.addWidget(self.table, 1)

        self.count_label = QLabel()
        outer.addWidget(self.count_label)

        self.add_btn.clicked.connect(self.add_job)
        self.edit_btn.clicked.connect(self.edit_job)
        self.delete_btn.clicked.connect(self.delete_job)
        self.invoice_btn.clicked.connect(self.invoice_for_job)
        self.refresh_btn.clicked.connect(self.refresh)
        self.table.doubleClicked.connect(lambda _idx: self.edit_job())
        self.search.textChanged.connect(self.refresh)
        self.activity.currentIndexChanged.connect(self.refresh)

        self._shortcut("Ctrl+N", self.add_job)
        self._shortcut("Ctrl+F", self.search.setFocus)
        self._shortcut("Delete", self.delete_job)
        self._shortcut("F5", self.refresh)
        self.refresh()

    def _shortcut(self, keys: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)

    def selected_id(self) -> int | None:
        index = self.table.currentIndex()
        return self.model.row_id(index.row()) if index.isValid() else None

    def refresh(self, *_args, select_id: int | None = None) -> None:
        keep_id = select_id if select_id is not None else self.selected_id()
        rows = self.repo.list_jobs(
            activity=self.activity.currentData(),
            search=self.search.text(),
        )
        self.model.replace(rows)
        self.count_label.setText(f"Zakázky: {len(rows)}")
        if keep_id is not None:
            for row, item in enumerate(rows):
                if item["id"] == keep_id:
                    self.table.selectRow(row)
                    break
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def add_job(self) -> None:
        dialog = JobDialog(self.repo, parent=self)
        if dialog.exec():
            data = dialog.data()
            job_id = self.repo.save_job(data)
            if data.get("source"):
                self.repo.add_lookup_value("customer_source", data["source"])
            self.refresh(select_id=job_id)
            self.data_changed.emit()

    def edit_job(self) -> None:
        job_id = self.selected_id()
        if not job_id:
            return
        job = self.repo.get_job(job_id)
        if not job:
            return
        dialog = JobDialog(self.repo, job, self)
        if dialog.exec():
            data = dialog.data()
            self.repo.save_job(data, job_id)
            if data.get("source"):
                self.repo.add_lookup_value("customer_source", data["source"])
            self.refresh(select_id=job_id)
            self.data_changed.emit()

    def delete_job(self) -> None:
        job_id = self.selected_id()
        if not job_id:
            return
        answer = QMessageBox.question(
            self,
            "Přesunout do koše",
            "Přesunout vybranou zakázku do koše? Data se fyzicky nesmažou.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.soft_delete_job(job_id)
            self.refresh()
            self.data_changed.emit()

    def invoice_for_job(self) -> None:
        job_id = self.selected_id()
        if not job_id:
            QMessageBox.information(self, "Faktura", "Nejdřív vyber zakázku.")
            return
        try:
            invoice_id = self.repo.create_invoice_from_job(job_id)
            invoice = self.repo.get_invoice(invoice_id)
            dialog = InvoiceDialog(self.repo, invoice, self)
            if dialog.exec():
                data, items = dialog.data_and_items()
                self.repo.save_invoice(invoice_id, data, items)
            self.refresh(select_id=job_id)
            self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Faktura", str(exc))


class ClientsWidget(QWidget):
    data_changed = Signal()

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        outer = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.add_btn = QPushButton("+ Nový klient")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        self.refresh_btn = QPushButton("Obnovit")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hledat klienta, telefon, e-mail, adresu, IČO…")
        for w in (self.add_btn, self.edit_btn, self.delete_btn, self.refresh_btn):
            bar.addWidget(w)
        bar.addWidget(self.search, 1)
        outer.addLayout(bar)

        self.model = DictTableModel(
            [
                Column("favorite", "★", lambda v, r: "★" if v else ""),
                Column("regular", "Stálý", lambda v, r: "Ano" if v else ""),
                Column("name", "Jméno"),
                Column("company_name", "Firma"),
                Column("phone", "Telefon"),
                Column("email", "E-mail"),
                Column("address", "Adresa"),
                Column("activity_scope", "Činnost", lambda v, r: "DDD + Dočista" if v == "BOTH" else ACTIVITY_LABELS.get(v, v)),
                Column("source", "Zdroj"),
                Column("job_count", "Zakázky", alignment=RIGHT),
                Column("spent_cents", "Celkem", _money, RIGHT),
                Column("last_job_date", "Poslední zakázka"),
            ]
        )
        self.table = QTableView()
        _setup_table(self.table, self.model)
        outer.addWidget(self.table, 1)
        self.count_label = QLabel()
        outer.addWidget(self.count_label)

        self.add_btn.clicked.connect(self.add_client)
        self.edit_btn.clicked.connect(self.edit_client)
        self.delete_btn.clicked.connect(self.delete_client)
        self.refresh_btn.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.table.doubleClicked.connect(lambda _idx: self.edit_client())

        self._shortcut("Ctrl+N", self.add_client)
        self._shortcut("Ctrl+F", self.search.setFocus)
        self._shortcut("Delete", self.delete_client)
        self._shortcut("F5", self.refresh)
        self.refresh()

    def _shortcut(self, keys: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)

    def selected_id(self) -> int | None:
        index = self.table.currentIndex()
        return self.model.row_id(index.row()) if index.isValid() else None

    def refresh(self, *_args, select_id: int | None = None) -> None:
        keep_id = select_id if select_id is not None else self.selected_id()
        rows = self.repo.list_clients(self.search.text())
        self.model.replace(rows)
        self.count_label.setText(f"Klienti: {len(rows)}")
        if keep_id is not None:
            for row, item in enumerate(rows):
                if item["id"] == keep_id:
                    self.table.selectRow(row)
                    break
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def add_client(self) -> None:
        dialog = ClientDialog(self.repo, parent=self)
        if dialog.exec():
            data = dialog.data()
            client_id = self.repo.save_client(data)
            if data.get("source"):
                self.repo.add_lookup_value("customer_source", data["source"])
            self.refresh(select_id=client_id)
            self.data_changed.emit()

    def edit_client(self) -> None:
        client_id = self.selected_id()
        if not client_id:
            return
        client = self.repo.get_client(client_id)
        if not client:
            return
        dialog = ClientDialog(self.repo, client, self)
        if dialog.exec():
            data = dialog.data()
            self.repo.save_client(data, client_id)
            if data.get("source"):
                self.repo.add_lookup_value("customer_source", data["source"])
            self.refresh(select_id=client_id)
            self.data_changed.emit()

    def delete_client(self) -> None:
        client_id = self.selected_id()
        if not client_id:
            return
        answer = QMessageBox.question(
            self,
            "Přesunout do koše",
            "Přesunout klienta do koše? Jeho staré zakázky zůstanou zachované.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.soft_delete_client(client_id)
            self.refresh()
            self.data_changed.emit()


class InvoicesWidget(QWidget):
    data_changed = Signal()

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        outer = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.edit_btn = QPushButton("Upravit")
        self.pdf_btn = QPushButton("PDF")
        self.delete_btn = QPushButton("Smazat")
        self.refresh_btn = QPushButton("Obnovit")
        self.activity = QComboBox()
        for code in ("ALL", "DDD", "DOCISTA"):
            self.activity.addItem(ACTIVITY_LABELS[code], code)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hledat číslo faktury, odběratele, adresu, IČO…")
        for w in (self.edit_btn, self.pdf_btn, self.delete_btn, self.refresh_btn):
            bar.addWidget(w)
        bar.addSpacing(10)
        bar.addWidget(QLabel("Činnost:"))
        bar.addWidget(self.activity)
        bar.addWidget(self.search, 1)
        outer.addLayout(bar)

        self.model = DictTableModel(
            [
                Column("number", "Číslo"),
                Column("issue_date", "Vystavení"),
                Column("due_date", "Splatnost"),
                Column("activity", "Činnost", _activity),
                Column("buyer_name", "Odběratel"),
                Column("buyer_address", "Adresa"),
                Column("total_cents", "Celkem", _money, RIGHT),
                Column("payment_method", "Platba", _payment_method),
                Column("payment_status", "Stav", _payment_status),
                Column("paid_at", "Zaplaceno dne"),
            ]
        )
        self.table = QTableView()
        _setup_table(self.table, self.model)
        outer.addWidget(self.table, 1)
        self.count_label = QLabel()
        outer.addWidget(self.count_label)

        self.edit_btn.clicked.connect(self.edit_invoice)
        self.pdf_btn.clicked.connect(self.export_pdf)
        self.delete_btn.clicked.connect(self.delete_invoice)
        self.refresh_btn.clicked.connect(self.refresh)
        self.activity.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.table.doubleClicked.connect(lambda _idx: self.edit_invoice())

        self._shortcut("Ctrl+F", self.search.setFocus)
        self._shortcut("Delete", self.delete_invoice)
        self._shortcut("F5", self.refresh)
        self.refresh()

    def _shortcut(self, keys: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)

    def selected_id(self) -> int | None:
        index = self.table.currentIndex()
        return self.model.row_id(index.row()) if index.isValid() else None

    def refresh(self, *_args, select_id: int | None = None) -> None:
        keep_id = select_id if select_id is not None else self.selected_id()
        rows = self.repo.list_invoices(
            activity=self.activity.currentData(),
            search=self.search.text(),
        )
        self.model.replace(rows)
        self.count_label.setText(f"Faktury: {len(rows)}")
        if keep_id is not None:
            for row, item in enumerate(rows):
                if item["id"] == keep_id:
                    self.table.selectRow(row)
                    break
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def edit_invoice(self) -> None:
        invoice_id = self.selected_id()
        if not invoice_id:
            return
        invoice = self.repo.get_invoice(invoice_id)
        if not invoice:
            return
        dialog = InvoiceDialog(self.repo, invoice, self)
        if dialog.exec():
            data, items = dialog.data_and_items()
            try:
                self.repo.save_invoice(invoice_id, data, items)
            except Exception as exc:
                QMessageBox.critical(self, "Faktura", str(exc))
                return
            self.refresh(select_id=invoice_id)
            self.data_changed.emit()

    def export_pdf(self) -> None:
        invoice_id = self.selected_id()
        if not invoice_id:
            return
        invoice = self.repo.get_invoice(invoice_id)
        if not invoice:
            return
        default = export_dir() / f"faktura-{invoice['number']}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Uložit fakturu PDF", str(default), "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            result = generate_invoice_pdf(self.repo, invoice_id, Path(path))
            QMessageBox.information(self, "PDF", f"Faktura uložena:\n{result}")
        except Exception as exc:
            QMessageBox.critical(self, "PDF", str(exc))

    def delete_invoice(self) -> None:
        invoice_id = self.selected_id()
        if not invoice_id:
            return
        answer = QMessageBox.question(
            self,
            "Přesunout do koše",
            "Přesunout fakturu do koše? Zakázka zůstane zachovaná.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.soft_delete_invoice(invoice_id)
            self.refresh()
            self.data_changed.emit()


class StatsWidget(QWidget):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        outer = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.activity = QComboBox()
        for code in ("ALL", "DDD", "DOCISTA"):
            self.activity.addItem(ACTIVITY_LABELS[code], code)
        self.year = QComboBox()
        self.year.addItem("Všechny roky", None)
        current = date.today().year
        for y in range(current, current - 10, -1):
            self.year.addItem(str(y), y)
        self.year.setCurrentIndex(1)
        bar.addWidget(QLabel("Činnost:"))
        bar.addWidget(self.activity)
        bar.addWidget(QLabel("Rok:"))
        bar.addWidget(self.year)
        bar.addStretch(1)
        outer.addLayout(bar)

        body = QHBoxLayout()
        self.month_table = QTableWidget(0, 3)
        self.month_table.setHorizontalHeaderLabels(["Měsíc", "Zakázky", "Celkem"])
        self.month_table.horizontalHeader().setStretchLastSection(True)
        self.month_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        body.addWidget(self._group("Po měsících", self.month_table), 1)

        self.service_table = QTableWidget(0, 3)
        self.service_table.setHorizontalHeaderLabels(["Typ", "Zakázky", "Celkem"])
        self.service_table.horizontalHeader().setStretchLastSection(True)
        self.service_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        body.addWidget(self._group("Služby / škůdci", self.service_table), 1)

        self.source_table = QTableWidget(0, 3)
        self.source_table.setHorizontalHeaderLabels(["Zdroj", "Zakázky", "Celkem"])
        self.source_table.horizontalHeader().setStretchLastSection(True)
        self.source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        body.addWidget(self._group("Zdroje", self.source_table), 1)
        outer.addLayout(body, 1)

        self.activity.currentIndexChanged.connect(self.refresh)
        self.year.currentIndexChanged.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _group(title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    def refresh(self, *_args) -> None:
        year = self.year.currentData()
        from_date = f"{year}-01-01" if year else None
        to_date = f"{year}-12-31" if year else None
        rows = self.repo.list_jobs(
            activity=self.activity.currentData(),
            from_date=from_date,
            to_date=to_date,
        )

        monthly = defaultdict(lambda: [0, 0])
        services = defaultdict(lambda: [0, 0])
        for row in rows:
            month = (row.get("job_date") or "")[:7] or "(bez data)"
            total = int(row.get("total_cents") or 0)
            monthly[month][0] += 1
            monthly[month][1] += total

            if row.get("activity") == "DDD":
                key = row.get("ddd_pest") or row.get("service_summary") or "(neuvedeno)"
            else:
                key = row.get("doc_cleaning_type") or row.get("service_summary") or "(neuvedeno)"
            services[key][0] += 1
            services[key][1] += total

        monthly_rows = sorted(monthly.items(), reverse=True)
        self.month_table.setRowCount(len(monthly_rows))
        for r, (key, values) in enumerate(monthly_rows):
            for c, value in enumerate((key, values[0], cents_to_text(values[1]))):
                self.month_table.setItem(r, c, QTableWidgetItem(str(value)))

        service_rows = sorted(services.items(), key=lambda x: x[1][1], reverse=True)
        self.service_table.setRowCount(len(service_rows))
        for r, (key, values) in enumerate(service_rows):
            for c, value in enumerate((key, values[0], cents_to_text(values[1]))):
                self.service_table.setItem(r, c, QTableWidgetItem(str(value)))

        sources = self.repo.source_breakdown(self.activity.currentData(), from_date, to_date)
        self.source_table.setRowCount(len(sources))
        for r, item in enumerate(sources):
            for c, value in enumerate(
                (item["source_name"], item["job_count"], cents_to_text(item["total_cents"]))
            ):
                self.source_table.setItem(r, c, QTableWidgetItem(str(value)))


class SettingsWidget(QWidget):
    data_changed = Signal()

    def __init__(self, repo, db, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.db = db

        outer = QVBoxLayout(self)
        seller = QGroupBox("Údaje dodavatele pro faktury")
        form = QFormLayout(seller)
        self.fields: dict[str, QLineEdit] = {}
        definitions = [
            ("seller_name", "Jméno / firma"),
            ("seller_address", "Adresa"),
            ("seller_ico", "IČO"),
            ("seller_dic", "DIČ"),
            ("seller_phone", "Telefon"),
            ("seller_email", "E-mail"),
            ("seller_bank_account", "Bankovní účet"),
        ]
        for key, label in definitions:
            edit = QLineEdit()
            self.fields[key] = edit
            form.addRow(label + ":", edit)

        self.due_days = QSpinBox()
        self.due_days.setRange(0, 365)
        self.number_digits = QSpinBox()
        self.number_digits.setRange(1, 8)
        form.addRow("Výchozí splatnost:", self.due_days)
        form.addRow("Počet číslic faktury:", self.number_digits)
        outer.addWidget(seller)

        source_group = QGroupBox("Zdroje zákazníků")
        source_layout = QVBoxLayout(source_group)
        self.source_list = QLabel()
        self.source_list.setWordWrap(True)
        source_layout.addWidget(self.source_list)
        source_row = QHBoxLayout()
        self.new_source = QLineEdit()
        self.new_source.setPlaceholderText("Nový zdroj")
        add_source = QPushButton("Přidat")
        add_source.clicked.connect(self.add_source)
        source_row.addWidget(self.new_source, 1)
        source_row.addWidget(add_source)
        source_layout.addLayout(source_row)
        outer.addWidget(source_group)

        buttons = QHBoxLayout()
        save = QPushButton("Uložit nastavení")
        backup = QPushButton("Vytvořit zálohu")
        integrity = QPushButton("Kontrola databáze")
        save.clicked.connect(self.save)
        backup.clicked.connect(self.backup)
        integrity.clicked.connect(self.integrity)
        buttons.addWidget(save)
        buttons.addWidget(backup)
        buttons.addWidget(integrity)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self.info = QLabel()
        self.info.setWordWrap(True)
        outer.addWidget(self.info)
        outer.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        settings = self.repo.get_settings()
        for key, edit in self.fields.items():
            edit.setText(settings.get(key, ""))
        try:
            self.due_days.setValue(int(settings.get("invoice_due_days", "14")))
        except ValueError:
            self.due_days.setValue(14)
        try:
            self.number_digits.setValue(int(settings.get("invoice_number_digits", "3")))
        except ValueError:
            self.number_digits.setValue(3)
        self._refresh_sources()
        self.info.setText(
            f"Databáze: {self.db.path}\n"
            f"Schema: {self.db.schema_version()}\n"
            f"Zálohy: {backup_dir()}"
        )

    def _refresh_sources(self) -> None:
        values = self.repo.list_lookup("customer_source")
        self.source_list.setText(" • ".join(values))

    def save(self) -> None:
        values = {key: edit.text().strip() for key, edit in self.fields.items()}
        values["invoice_due_days"] = str(self.due_days.value())
        values["invoice_number_digits"] = str(self.number_digits.value())
        self.repo.save_settings(values)
        QMessageBox.information(self, "Nastavení", "Nastavení bylo uloženo.")
        self.data_changed.emit()

    def add_source(self) -> None:
        value = self.new_source.text().strip()
        if not value:
            return
        self.repo.add_lookup_value("customer_source", value)
        self.new_source.clear()
        self._refresh_sources()
        self.data_changed.emit()

    def backup(self) -> None:
        try:
            target = create_backup(self.db, backup_dir(), prefix="manual")
            QMessageBox.information(self, "Záloha", f"Záloha vytvořena:\n{target}")
        except Exception as exc:
            QMessageBox.critical(self, "Záloha", str(exc))

    def integrity(self) -> None:
        result = self.db.integrity_check()
        if result == "ok":
            QMessageBox.information(self, "Databáze", "Kontrola databáze: OK")
        else:
            QMessageBox.warning(self, "Databáze", f"Výsledek kontroly: {result}")
