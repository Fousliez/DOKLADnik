from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate


ACTIVITY_LABELS = {
    "ALL": "Vše",
    "DDD": "DDD",
    "DOCISTA": "Dočista",
}

PAYMENT_METHOD_LABELS = {
    "CASH": "Hotovost",
    "BANK": "Převod",
    "CARD": "Karta",
}

PAYMENT_STATUS_LABELS = {
    "UNPAID": "Nezaplaceno",
    "PARTIAL": "Částečně",
    "PAID": "Zaplaceno",
}

DOCUMENT_LABELS = {
    "NONE": "Bez dokladu",
    "RECEIPT": "Účtenka",
    "INVOICE": "Faktura",
}


def cents_to_text(cents: int | float | None) -> str:
    cents = int(cents or 0)
    amount = cents / 100
    if cents % 100:
        return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " Kč"
    return f"{int(amount):,}".replace(",", " ") + " Kč"


def money_to_cents(text: str) -> int:
    clean = (
        str(text)
        .replace("Kč", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace(",", ".")
        .strip()
    )
    if not clean:
        return 0
    return int(round(float(clean) * 100))


def iso_to_qdate(value: str | None) -> QDate:
    if not value:
        return QDate.currentDate()
    parsed = QDate.fromString(str(value), "yyyy-MM-dd")
    return parsed if parsed.isValid() else QDate.currentDate()


def qdate_to_iso(value: QDate) -> str:
    return value.toString("yyyy-MM-dd")


def today_iso() -> str:
    return date.today().isoformat()
