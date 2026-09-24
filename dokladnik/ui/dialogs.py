from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .common import (
    DOCUMENT_LABELS,
    PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS,
    cents_to_text,
    iso_to_qdate,
    money_to_cents,
    qdate_to_iso,
)


def _add_code_items(combo: QComboBox, mapping: dict[str, str]) -> None:
    for code, label in mapping.items():
        combo.addItem(label, code)


def _set_combo_code(combo: QComboBox, code: str | None) -> None:
    index = combo.findData(code)
    if index >= 0:
        combo.setCurrentIndex(index)


def _money_edit(cents: int | None = None) -> QLineEdit:
    edit = QLineEdit()
    edit.setAlignment(Qt.AlignmentFlag.AlignRight)
    edit.setPlaceholderText("0")
    if cents:
        edit.setText(f"{int(cents) / 100:.2f}".replace(".", ",").rstrip("0").rstrip(","))
    return edit


class ClientDialog(QDialog):
    def __init__(self, repo, client: dict | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.client = client or {}
        self.setWindowTitle("Klient")
        self.resize(580, 650)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.company_name = QLineEdit()
        self.contact_person = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QTextEdit()
        self.address.setMaximumHeight(65)
        self.billing_address = QTextEdit()
        self.billing_address.setMaximumHeight(65)
        self.ico = QLineEdit()
        self.dic = QLineEdit()

        self.activity_scope = QComboBox()
        self.activity_scope.addItem("DDD + Dočista", "BOTH")
        self.activity_scope.addItem("DDD", "DDD")
        self.activity_scope.addItem("Dočista", "DOCISTA")

        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.addItems(self.repo.list_lookup("customer_source"))

        self.favorite = QCheckBox("Oblíbený klient")
        self.regular = QCheckBox("Stálý klient")
        flags = QHBoxLayout()
        flags.addWidget(self.favorite)
        flags.addWidget(self.regular)
        flags.addStretch(1)
        flags_widget = QWidget()
        flags_widget.setLayout(flags)

        self.note = QTextEdit()
        self.note.setMinimumHeight(100)

        form.addRow("Jméno:", self.name)
        form.addRow("Firma:", self.company_name)
        form.addRow("Kontaktní osoba:", self.contact_person)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("Adresa:", self.address)
        form.addRow("Fakturační adresa:", self.billing_address)
        form.addRow("IČO:", self.ico)
        form.addRow("DIČ:", self.dic)
        form.addRow("Činnost:", self.activity_scope)
        form.addRow("Zdroj:", self.source)
        form.addRow("", flags_widget)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Uložit")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Zrušit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self.accept)
        self._load()

    def _load(self) -> None:
        c = self.client
        self.name.setText(c.get("name") or "")
        self.company_name.setText(c.get("company_name") or "")
        self.contact_person.setText(c.get("contact_person") or "")
        self.phone.setText(c.get("phone") or "")
        self.email.setText(c.get("email") or "")
        self.address.setPlainText(c.get("address") or "")
        self.billing_address.setPlainText(c.get("billing_address") or "")
        self.ico.setText(c.get("ico") or "")
        self.dic.setText(c.get("dic") or "")
        _set_combo_code(self.activity_scope, c.get("activity_scope") or "BOTH")
        self.source.setCurrentText(c.get("source") or "")
        self.favorite.setChecked(bool(c.get("favorite")))
        self.regular.setChecked(bool(c.get("regular")))
        self.note.setPlainText(c.get("note") or "")

    def accept(self) -> None:
        if not self.name.text().strip() and not self.company_name.text().strip():
            QMessageBox.warning(self, "Chybí klient", "Vyplň jméno nebo název firmy.")
            return
        super().accept()

    def data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "company_name": self.company_name.text().strip(),
            "contact_person": self.contact_person.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "address": self.address.toPlainText().strip(),
            "billing_address": self.billing_address.toPlainText().strip(),
            "ico": self.ico.text().strip(),
            "dic": self.dic.text().strip(),
            "activity_scope": self.activity_scope.currentData(),
            "favorite": self.favorite.isChecked(),
            "regular": self.regular.isChecked(),
            "source": self.source.currentText().strip(),
            "note": self.note.toPlainText().strip(),
        }


class JobDialog(QDialog):
    def __init__(self, repo, job: dict | None = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job = job or {}
        self._loading = True
        self.setWindowTitle("Zakázka")
        self.resize(1040, 820)
        self.setMinimumSize(820, 650)

        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        page = QWidget()
        scroll.setWidget(page)
        page_layout = QVBoxLayout(page)

        top_row = QHBoxLayout()
        page_layout.addLayout(top_row)

        # Základ zakázky
        basic_group = QGroupBox("Zakázka")
        basic_form = QFormLayout(basic_group)

        self.job_date = QDateEdit()
        self.job_date.setCalendarPopup(True)
        self.job_date.setDisplayFormat("dd.MM.yyyy")

        self.activity = QComboBox()
        self.activity.addItem("DDD", "DDD")
        self.activity.addItem("Dočista", "DOCISTA")

        self.client = QComboBox()
        self.client.addItem("(bez vazby na klienta)", None)
        self._clients = self.repo.list_clients()
        for c in self._clients:
            title = c.get("company_name") or c.get("name") or f"Klient #{c['id']}"
            prefix = "★ " if c.get("favorite") else ("● " if c.get("regular") else "")
            self.client.addItem(prefix + title, c["id"])

        self.customer_name = QLineEdit()
        self.service_address = QTextEdit()
        self.service_address.setMaximumHeight(62)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.service_summary = QLineEdit()

        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.addItems(self.repo.list_lookup("customer_source"))

        basic_form.addRow("Datum:", self.job_date)
        basic_form.addRow("Činnost:", self.activity)
        basic_form.addRow("Klient:", self.client)
        basic_form.addRow("Jméno / kontakt:", self.customer_name)
        basic_form.addRow("Adresa zakázky:", self.service_address)
        basic_form.addRow("Telefon:", self.phone)
        basic_form.addRow("E-mail:", self.email)
        basic_form.addRow("Co se dělalo:", self.service_summary)
        basic_form.addRow("Zdroj zákazníka:", self.source)
        top_row.addWidget(basic_group, 1)

        # Platba a doklad
        payment_group = QGroupBox("Platba a doklad")
        pay_form = QFormLayout(payment_group)

        self.price = _money_edit()
        self.tip = _money_edit()
        self.travel = _money_edit()

        self.distance = QDoubleSpinBox()
        self.distance.setRange(0, 1000000)
        self.distance.setDecimals(1)
        self.distance.setSuffix(" km")

        self.payment_method = QComboBox()
        _add_code_items(self.payment_method, PAYMENT_METHOD_LABELS)

        self.payment_status = QComboBox()
        _add_code_items(self.payment_status, PAYMENT_STATUS_LABELS)

        self.paid_at = QDateEdit()
        self.paid_at.setCalendarPopup(True)
        self.paid_at.setDisplayFormat("dd.MM.yyyy")

        self.document_type = QComboBox()
        _add_code_items(self.document_type, DOCUMENT_LABELS)

        self.invoice_number = QLineEdit()
        self.invoice_number.setReadOnly(True)

        pay_form.addRow("Cena práce:", self.price)
        pay_form.addRow("Dýško:", self.tip)
        pay_form.addRow("Cestovné:", self.travel)
        pay_form.addRow("Ujeto:", self.distance)
        pay_form.addRow("Platba:", self.payment_method)
        pay_form.addRow("Stav:", self.payment_status)
        pay_form.addRow("Datum zaplacení:", self.paid_at)
        pay_form.addRow("Doklad:", self.document_type)
        pay_form.addRow("Číslo faktury:", self.invoice_number)
        top_row.addWidget(payment_group, 1)

        # DDD
        self.ddd_group = QGroupBox("DDD – detail zásahu")
        ddd_form = QFormLayout(self.ddd_group)
        self.ddd_intervention_type = QLineEdit()
        self.ddd_pest = QLineEdit()
        self.ddd_protocol = QCheckBox("Protokol vystaven")
        self.ddd_protocol_no = QLineEdit()
        self.ddd_stage = QLineEdit()
        self.ddd_next_enabled = QCheckBox("Naplánovaný další zásah")
        self.ddd_next_visit = QDateEdit()
        self.ddd_next_visit.setCalendarPopup(True)
        self.ddd_next_visit.setDisplayFormat("dd.MM.yyyy")
        next_row = QHBoxLayout()
        next_row.addWidget(self.ddd_next_enabled)
        next_row.addWidget(self.ddd_next_visit)
        next_row.addStretch(1)
        next_widget = QWidget()
        next_widget.setLayout(next_row)

        ddd_form.addRow("Typ zásahu:", self.ddd_intervention_type)
        ddd_form.addRow("Škůdce:", self.ddd_pest)
        ddd_form.addRow("", self.ddd_protocol)
        ddd_form.addRow("Číslo protokolu:", self.ddd_protocol_no)
        ddd_form.addRow("Fáze / opakování:", self.ddd_stage)
        ddd_form.addRow("Další zásah:", next_widget)
        page_layout.addWidget(self.ddd_group)

        # Dočista
        self.doc_group = QGroupBox("Dočista – detail čištění")
        doc_form = QFormLayout(self.doc_group)
        self.doc_cleaning_type = QLineEdit()
        self.doc_quantity = QDoubleSpinBox()
        self.doc_quantity.setRange(0, 100000)
        self.doc_quantity.setDecimals(1)
        self.doc_area = QDoubleSpinBox()
        self.doc_area.setRange(0, 100000)
        self.doc_area.setDecimals(1)
        self.doc_area.setSuffix(" m²")

        doc_form.addRow("Typ čištění:", self.doc_cleaning_type)
        doc_form.addRow("Počet kusů:", self.doc_quantity)
        doc_form.addRow("Plocha:", self.doc_area)
        page_layout.addWidget(self.doc_group)

        # Poznámka je součást stejného formuláře
        note_group = QGroupBox("Poznámka")
        note_layout = QVBoxLayout(note_group)
        self.note = QTextEdit()
        self.note.setMinimumHeight(110)
        self.note.setPlaceholderText("Poznámky k zakázce…")
        note_layout.addWidget(self.note)
        page_layout.addWidget(note_group)

        page_layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Uložit")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Zrušit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self.activity.currentIndexChanged.connect(self._activity_changed)
        self.client.currentIndexChanged.connect(self._client_changed)
        self.payment_status.currentIndexChanged.connect(self._payment_status_changed)
        self.ddd_next_enabled.toggled.connect(self.ddd_next_visit.setEnabled)
        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self.accept)

        self._load()
        self._loading = False
        self._activity_changed()
        self._payment_status_changed()

    def _load(self) -> None:
        j = self.job
        self.job_date.setDate(iso_to_qdate(j.get("job_date")))
        _set_combo_code(self.activity, j.get("activity") or "DDD")

        if j.get("client_id"):
            idx = self.client.findData(j.get("client_id"))
            if idx >= 0:
                self.client.setCurrentIndex(idx)

        self.customer_name.setText(j.get("customer_name") or "")
        self.service_address.setPlainText(j.get("service_address") or "")
        self.phone.setText(j.get("phone") or "")
        self.email.setText(j.get("email") or "")
        self.service_summary.setText(j.get("service_summary") or "")
        self.source.setCurrentText(j.get("source") or "")

        self.price.setText(self._editable_money(j.get("price_cents")))
        self.tip.setText(self._editable_money(j.get("tip_cents")))
        self.travel.setText(self._editable_money(j.get("travel_cents")))
        self.distance.setValue(float(j.get("distance_km") or 0))
        _set_combo_code(self.payment_method, j.get("payment_method") or "CASH")
        _set_combo_code(self.payment_status, j.get("payment_status") or "PAID")
        self.paid_at.setDate(iso_to_qdate(j.get("paid_at") or j.get("job_date")))
        _set_combo_code(self.document_type, j.get("document_type") or "NONE")
        self.invoice_number.setText(j.get("invoice_number") or "")

        self.ddd_intervention_type.setText(j.get("ddd_intervention_type") or "")
        self.ddd_pest.setText(j.get("ddd_pest") or "")
        self.ddd_protocol.setChecked(bool(j.get("ddd_protocol")))
        self.ddd_protocol_no.setText(j.get("ddd_protocol_no") or "")
        self.ddd_stage.setText(j.get("ddd_stage") or "")
        self.ddd_next_enabled.setChecked(bool(j.get("ddd_next_visit")))
        self.ddd_next_visit.setDate(iso_to_qdate(j.get("ddd_next_visit")))
        self.ddd_next_visit.setEnabled(bool(j.get("ddd_next_visit")))

        self.doc_cleaning_type.setText(j.get("doc_cleaning_type") or "")
        self.doc_quantity.setValue(float(j.get("doc_quantity") or 0))
        self.doc_area.setValue(float(j.get("doc_area_m2") or 0))
        self.note.setPlainText(j.get("note") or "")

    @staticmethod
    def _editable_money(cents) -> str:
        cents = int(cents or 0)
        if not cents:
            return ""
        value = cents / 100
        return f"{value:.2f}".replace(".", ",").rstrip("0").rstrip(",")

    def _activity_changed(self) -> None:
        ddd = self.activity.currentData() == "DDD"
        self.ddd_group.setVisible(ddd)
        self.doc_group.setVisible(not ddd)

    def _payment_status_changed(self) -> None:
        self.paid_at.setEnabled(self.payment_status.currentData() == "PAID")

    def _client_changed(self) -> None:
        if self._loading:
            return
        client_id = self.client.currentData()
        if not client_id:
            return
        c = next((x for x in self._clients if x["id"] == client_id), None)
        if not c:
            return
        self.customer_name.setText(c.get("company_name") or c.get("name") or "")
        self.service_address.setPlainText(c.get("address") or "")
        self.phone.setText(c.get("phone") or "")
        self.email.setText(c.get("email") or "")
        if c.get("source"):
            self.source.setCurrentText(c["source"])

    def accept(self) -> None:
        try:
            money_to_cents(self.price.text())
            money_to_cents(self.tip.text())
            money_to_cents(self.travel.text())
        except ValueError:
            QMessageBox.warning(self, "Neplatná částka", "Částky musí být čísla.")
            return
        if not self.customer_name.text().strip() and not self.service_summary.text().strip():
            answer = QMessageBox.question(
                self,
                "Prázdná zakázka",
                "Zakázka nemá jméno ani popis práce. Opravdu ji uložit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().accept()

    def data(self) -> dict:
        return {
            "job_date": qdate_to_iso(self.job_date.date()),
            "activity": self.activity.currentData(),
            "client_id": self.client.currentData(),
            "customer_name": self.customer_name.text().strip(),
            "service_address": self.service_address.toPlainText().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "service_summary": self.service_summary.text().strip(),
            "price_cents": money_to_cents(self.price.text()),
            "tip_cents": money_to_cents(self.tip.text()),
            "travel_cents": money_to_cents(self.travel.text()),
            "distance_km": self.distance.value(),
            "payment_method": self.payment_method.currentData(),
            "payment_status": self.payment_status.currentData(),
            "paid_at": (
                qdate_to_iso(self.paid_at.date())
                if self.payment_status.currentData() == "PAID"
                else None
            ),
            "document_type": self.document_type.currentData(),
            "source": self.source.currentText().strip(),
            "note": self.note.toPlainText().strip(),
            "ddd_intervention_type": self.ddd_intervention_type.text().strip(),
            "ddd_pest": self.ddd_pest.text().strip(),
            "ddd_protocol": self.ddd_protocol.isChecked(),
            "ddd_protocol_no": self.ddd_protocol_no.text().strip(),
            "ddd_stage": self.ddd_stage.text().strip(),
            "ddd_next_visit": (
                qdate_to_iso(self.ddd_next_visit.date())
                if self.ddd_next_enabled.isChecked()
                else None
            ),
            "doc_cleaning_type": self.doc_cleaning_type.text().strip(),
            "doc_quantity": self.doc_quantity.value(),
            "doc_area_m2": self.doc_area.value(),
        }


class InvoiceDialog(QDialog):
    def __init__(self, repo, invoice: dict, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.invoice = invoice
        self._updating = False
        self.setWindowTitle(f"Faktura {invoice.get('number', '')}")
        self.resize(780, 720)

        outer = QVBoxLayout(self)
        form = QFormLayout()

        self.number = QLineEdit()
        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDisplayFormat("dd.MM.yyyy")
        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("dd.MM.yyyy")
        self.buyer_name = QLineEdit()
        self.buyer_address = QTextEdit()
        self.buyer_address.setMaximumHeight(65)
        self.buyer_ico = QLineEdit()
        self.buyer_dic = QLineEdit()

        self.payment_method = QComboBox()
        _add_code_items(self.payment_method, PAYMENT_METHOD_LABELS)
        self.payment_status = QComboBox()
        _add_code_items(self.payment_status, PAYMENT_STATUS_LABELS)
        self.paid_at = QDateEdit()
        self.paid_at.setCalendarPopup(True)
        self.paid_at.setDisplayFormat("dd.MM.yyyy")

        form.addRow("Číslo faktury:", self.number)
        form.addRow("Vystavení:", self.issue_date)
        form.addRow("Splatnost:", self.due_date)
        form.addRow("Odběratel:", self.buyer_name)
        form.addRow("Adresa:", self.buyer_address)
        form.addRow("IČO:", self.buyer_ico)
        form.addRow("DIČ:", self.buyer_dic)
        form.addRow("Platba:", self.payment_method)
        form.addRow("Stav:", self.payment_status)
        form.addRow("Datum zaplacení:", self.paid_at)
        outer.addLayout(form)

        outer.addWidget(QLabel("<b>Položky</b>"))
        self.items = QTableWidget(0, 4)
        self.items.setHorizontalHeaderLabels(["Popis", "Množství", "Jednotka", "Cena / jednotka"])
        self.items.horizontalHeader().setStretchLastSection(False)
        self.items.horizontalHeader().setSectionResizeMode(0, self.items.horizontalHeader().ResizeMode.Stretch)
        outer.addWidget(self.items, 1)

        item_buttons = QHBoxLayout()
        add = QPushButton("+ Položka")
        remove = QPushButton("− Odebrat")
        add.clicked.connect(self._add_item)
        remove.clicked.connect(self._remove_item)
        item_buttons.addWidget(add)
        item_buttons.addWidget(remove)
        item_buttons.addStretch(1)
        self.total = QLabel()
        self.total.setStyleSheet("font-size: 16px; font-weight: bold;")
        item_buttons.addWidget(self.total)
        outer.addLayout(item_buttons)

        self.note = QTextEdit()
        self.note.setMaximumHeight(80)
        self.note.setPlaceholderText("Poznámka na faktuře")
        outer.addWidget(self.note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Uložit")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Zrušit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self.items.itemChanged.connect(self._update_total)
        self.payment_status.currentIndexChanged.connect(self._payment_status_changed)
        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self.accept)
        self._load()

    def _load(self) -> None:
        i = self.invoice
        self.number.setText(i.get("number") or "")
        self.issue_date.setDate(iso_to_qdate(i.get("issue_date")))
        self.due_date.setDate(iso_to_qdate(i.get("due_date")))
        self.buyer_name.setText(i.get("buyer_name") or "")
        self.buyer_address.setPlainText(i.get("buyer_address") or "")
        self.buyer_ico.setText(i.get("buyer_ico") or "")
        self.buyer_dic.setText(i.get("buyer_dic") or "")
        _set_combo_code(self.payment_method, i.get("payment_method") or "BANK")
        _set_combo_code(self.payment_status, i.get("payment_status") or "UNPAID")
        self.paid_at.setDate(iso_to_qdate(i.get("paid_at") or i.get("issue_date")))
        self.note.setPlainText(i.get("note") or "")
        self._updating = True
        for item in i.get("items", []):
            self._add_item(item)
        if self.items.rowCount() == 0:
            self._add_item()
        self._updating = False
        self._payment_status_changed()
        self._update_total()

    def _add_item(self, item: dict | None = None) -> None:
        item = item or {}
        row = self.items.rowCount()
        self.items.insertRow(row)
        values = [
            item.get("description") or "",
            f"{float(item.get('quantity') or 1):g}",
            item.get("unit") or "ks",
            JobDialog._editable_money(item.get("unit_price_cents")),
        ]
        for col, value in enumerate(values):
            self.items.setItem(row, col, QTableWidgetItem(str(value)))
        self._update_total()

    def _remove_item(self) -> None:
        row = self.items.currentRow()
        if row >= 0 and self.items.rowCount() > 1:
            self.items.removeRow(row)
            self._update_total()

    def _payment_status_changed(self) -> None:
        self.paid_at.setEnabled(self.payment_status.currentData() == "PAID")

    def _update_total(self, *_args) -> None:
        if self._updating:
            return
        total = 0
        try:
            for row in range(self.items.rowCount()):
                qty_item = self.items.item(row, 1)
                price_item = self.items.item(row, 3)
                qty = float((qty_item.text() if qty_item else "1").replace(",", ".") or 1)
                price = money_to_cents(price_item.text() if price_item else "")
                total += int(round(qty * price))
            self.total.setText("Celkem: " + cents_to_text(total))
        except ValueError:
            self.total.setText("Celkem: neplatná hodnota")

    def accept(self) -> None:
        if not self.number.text().strip():
            QMessageBox.warning(self, "Chybí číslo", "Faktura musí mít číslo.")
            return
        try:
            self.data_and_items()
        except ValueError:
            QMessageBox.warning(self, "Neplatná položka", "Zkontroluj množství a cenu položek.")
            return
        super().accept()

    def data_and_items(self) -> tuple[dict, list[dict]]:
        items = []
        for row in range(self.items.rowCount()):
            desc_item = self.items.item(row, 0)
            qty_item = self.items.item(row, 1)
            unit_item = self.items.item(row, 2)
            price_item = self.items.item(row, 3)
            quantity = float((qty_item.text() if qty_item else "1").replace(",", ".") or 1)
            price = money_to_cents(price_item.text() if price_item else "")
            items.append(
                {
                    "description": (desc_item.text() if desc_item else "").strip(),
                    "quantity": quantity,
                    "unit": (unit_item.text() if unit_item else "ks").strip() or "ks",
                    "unit_price_cents": price,
                }
            )

        data = {
            "number": self.number.text().strip(),
            "issue_date": qdate_to_iso(self.issue_date.date()),
            "due_date": qdate_to_iso(self.due_date.date()),
            "buyer_name": self.buyer_name.text().strip(),
            "buyer_address": self.buyer_address.toPlainText().strip(),
            "buyer_ico": self.buyer_ico.text().strip(),
            "buyer_dic": self.buyer_dic.text().strip(),
            "payment_method": self.payment_method.currentData(),
            "payment_status": self.payment_status.currentData(),
            "paid_at": (
                qdate_to_iso(self.paid_at.date())
                if self.payment_status.currentData() == "PAID"
                else ""
            ),
            "note": self.note.toPlainText().strip(),
        }
        return data, items
