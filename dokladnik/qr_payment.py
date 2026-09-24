from __future__ import annotations

import io
import re
from datetime import datetime
from urllib.parse import quote

import qrcode
from qrcode.constants import ERROR_CORRECT_M


_IBAN_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$")
_CZ_ACCOUNT_RE = re.compile(r"^(?:(?P<prefix>\d{1,6})-)?(?P<number>\d{1,10})/(?P<bank>\d{4})$")


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def validate_iban(value: str) -> bool:
    iban = normalize_iban(value)
    if not _IBAN_RE.fullmatch(iban):
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    try:
        return int(numeric) % 97 == 1
    except ValueError:
        return False


def czech_account_to_iban(value: str) -> str | None:
    compact = re.sub(r"\s+", "", str(value or ""))
    match = _CZ_ACCOUNT_RE.fullmatch(compact)
    if not match:
        return None

    prefix = (match.group("prefix") or "").zfill(6)
    number = match.group("number").zfill(10)
    bank = match.group("bank")
    bban = bank + prefix + number

    check = 98 - (int(bban + "123500") % 97)  # CZ00 -> 12 35 00
    iban = f"CZ{check:02d}{bban}"
    return iban if validate_iban(iban) else None


def resolve_iban(settings: dict[str, str]) -> str | None:
    explicit = normalize_iban(settings.get("seller_iban", ""))
    if explicit:
        return explicit if validate_iban(explicit) else None
    return czech_account_to_iban(settings.get("seller_bank_account", ""))


def invoice_number_to_vs(number: str) -> str | None:
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if 1 <= len(digits) <= 10:
        return digits
    return None


def build_spd(
    *,
    iban: str,
    amount_cents: int,
    due_date: str | None = None,
    invoice_number: str = "",
) -> str:
    iban = normalize_iban(iban)
    if not validate_iban(iban):
        raise ValueError("Neplatný IBAN pro QR platbu.")
    if amount_cents <= 0:
        raise ValueError("Částka QR platby musí být vyšší než 0.")

    attributes = [
        f"ACC:{iban}",
        f"AM:{amount_cents / 100:.2f}",
        "CC:CZK",
    ]

    if due_date:
        try:
            dt = datetime.strptime(str(due_date), "%Y-%m-%d")
            attributes.append(f"DT:{dt.strftime('%Y%m%d')}")
        except ValueError:
            pass

    message = f"FAKTURA {str(invoice_number or '').strip()}".strip()
    if message:
        encoded = quote(message[:60], safe=" -._")
        attributes.append(f"MSG:{encoded}")

    vs = invoice_number_to_vs(invoice_number)
    if vs:
        attributes.append(f"X-VS:{vs}")

    return "SPD*1.0*" + "*".join(attributes)


def qr_png_bytes(payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
