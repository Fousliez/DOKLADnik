from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtPrintSupport import QPrinter

from .qr_payment import build_spd, invoice_number_to_vs, qr_png_bytes, resolve_iban
from .repository import Repository


def format_czk(cents: int | float) -> str:
    amount = int(round(float(cents))) / 100
    text = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    if text.endswith(",00"):
        text = text[:-3]
    return f"{text} Kč"


def _e(value: object) -> str:
    return escape(str(value or ""))


def generate_invoice_pdf(repo: Repository, invoice_id: int, target: Path) -> Path:
    invoice = repo.get_invoice(invoice_id)
    if not invoice:
        raise KeyError("Faktura neexistuje.")

    seller = repo.get_settings()
    items = invoice.get("items", [])
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{_e(item.get('description'))}</td>"
            f"<td class='right'>{float(item.get('quantity') or 0):g} {_e(item.get('unit'))}</td>"
            f"<td class='right'>{format_czk(item.get('unit_price_cents') or 0)}</td>"
            f"<td class='right'>{format_czk(item.get('total_cents') or 0)}</td>"
            "</tr>"
        )

    total = sum(int(x.get("total_cents") or 0) for x in items)
    paid = invoice.get("payment_status") == "PAID"
    status = "ZAPLACENO" if paid else "NEZAPLACENO"

    qr_html = ""
    qr_image = None
    if bool(invoice.get("qr_payment")):
        iban = resolve_iban(seller)
        if not iban:
            raise ValueError(
                "QR platbu nelze vytvořit: v Nastavení chybí platný IBAN nebo český bankovní účet."
            )
        payload = build_spd(
            iban=iban,
            amount_cents=total,
            due_date=invoice.get("due_date"),
            invoice_number=invoice.get("number") or "",
        )
        qr_image = QImage.fromData(qr_png_bytes(payload), "PNG")
        if qr_image.isNull():
            raise ValueError("QR kód se nepodařilo vytvořit.")
        vs = invoice_number_to_vs(invoice.get("number") or "")
        vs_line = f"<br>VS: <b>{_e(vs)}</b>" if vs else ""
        qr_html = (
            "<table style='margin-top:12px;'>"
            "<tr>"
            "<td width='65%' style='vertical-align:middle;'>"
            "<b>QR platba</b><br>"
            "Naskenujte v mobilním bankovnictví."
            f"{vs_line}"
            "</td>"
            "<td width='35%' class='right'>"
            "<img src='dokladnik-qr.png' width='132' height='132'>"
            "</td>"
            "</tr>"
            "</table>"
        )

    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      body {{ font-family: sans-serif; font-size: 10pt; color: #222; }}
      h1 {{ font-size: 22pt; margin-bottom: 2px; }}
      h2 {{ font-size: 12pt; margin: 0 0 8px 0; }}
      table {{ width: 100%; border-collapse: collapse; }}
      td, th {{ padding: 6px; vertical-align: top; }}
      .items th {{ border-bottom: 1px solid #777; text-align: left; }}
      .items td {{ border-bottom: 1px solid #ddd; }}
      .right {{ text-align: right; }}
      .box {{ border: 1px solid #bbb; padding: 10px; }}
      .muted {{ color: #666; }}
      .total {{ font-size: 16pt; font-weight: bold; }}
      .status {{ font-size: 11pt; font-weight: bold; }}
    </style>
    </head>
    <body>
      <table>
        <tr>
          <td>
            <h1>FAKTURA</h1>
            <div class="muted">č. {_e(invoice.get('number'))}</div>
          </td>
          <td class="right">
            <div class="status">{status}</div>
          </td>
        </tr>
      </table>

      <br>
      <table>
        <tr>
          <td width="50%" class="box">
            <h2>Dodavatel</h2>
            <b>{_e(seller.get('seller_name'))}</b><br>
            {_e(seller.get('seller_address'))}<br>
            IČO: {_e(seller.get('seller_ico'))}<br>
            DIČ: {_e(seller.get('seller_dic'))}<br>
            Tel.: {_e(seller.get('seller_phone'))}<br>
            E-mail: {_e(seller.get('seller_email'))}
          </td>
          <td width="50%" class="box">
            <h2>Odběratel</h2>
            <b>{_e(invoice.get('buyer_name'))}</b><br>
            {_e(invoice.get('buyer_address'))}<br>
            IČO: {_e(invoice.get('buyer_ico'))}<br>
            DIČ: {_e(invoice.get('buyer_dic'))}
          </td>
        </tr>
      </table>

      <br>
      <table>
        <tr><td>Datum vystavení:</td><td><b>{_e(invoice.get('issue_date'))}</b></td></tr>
        <tr><td>Datum splatnosti:</td><td><b>{_e(invoice.get('due_date'))}</b></td></tr>
        <tr><td>Způsob úhrady:</td><td><b>{_e(invoice.get('payment_method'))}</b></td></tr>
        <tr><td>Účet:</td><td><b>{_e(seller.get('seller_bank_account'))}</b></td></tr>
      </table>

      <br>
      <table class="items">
        <tr>
          <th>Popis</th>
          <th class="right">Množství</th>
          <th class="right">Cena</th>
          <th class="right">Celkem</th>
        </tr>
        {''.join(rows)}
      </table>

      <br>
      <table>
        <tr>
          <td class="right">Celkem k úhradě:</td>
          <td class="right total">{format_czk(total)}</td>
        </tr>
      </table>

      {qr_html}

      <p>{_e(invoice.get('note'))}</p>
    </body>
    </html>
    """

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))

    document = QTextDocument()
    if qr_image is not None:
        document.addResource(
            QTextDocument.ResourceType.ImageResource,
            QUrl("dokladnik-qr.png"),
            qr_image,
        )
    document.setHtml(html)
    document.print_(printer)
    return target
