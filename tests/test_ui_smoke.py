from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from dokladnik.db import Database
from dokladnik.invoice_pdf import generate_invoice_pdf
from dokladnik.repository import Repository
from dokladnik.ui.dialogs import InvoiceDialog, JobDialog
from dokladnik.ui.main_window import MainWindow


class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "ui.sqlite3")
        self.db.initialize()
        self.repo = Repository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_invoice(self):
        client_id = self.repo.save_client({"name": "UI Test"})
        job_id = self.repo.save_job(
            {
                "job_date": "2026-09-24",
                "activity": "DDD",
                "client_id": client_id,
                "customer_name": "UI Test",
                "service_address": "Test 1",
                "service_summary": "Deratizace",
                "price_cents": 100000,
                "tip_cents": 0,
                "travel_cents": 10000,
                "payment_method": "BANK",
                "payment_status": "UNPAID",
                "document_type": "NONE",
                "source": "web",
            }
        )
        return job_id, self.repo.create_invoice_from_job(job_id)

    def test_main_window_constructs(self):
        window = MainWindow(self.repo, self.db)
        self.assertEqual(window.tabs.count(), 6)
        window.close()

    def test_job_and_invoice_dialogs_construct(self):
        job_id, invoice_id = self._seed_invoice()
        job = self.repo.get_job(job_id)
        invoice = self.repo.get_invoice(invoice_id)
        job_dialog = JobDialog(self.repo, job)
        invoice_dialog = InvoiceDialog(self.repo, invoice)
        self.assertEqual(job_dialog.customer_name.text(), "UI Test")
        self.assertFalse(job_dialog.detail_container.isVisible())
        self.assertFalse(job_dialog.invoice_combo.isEnabled())
        self.assertEqual(job_dialog.invoice_lock.text(), "🔒")
        self.assertTrue(invoice_dialog.number.text())
        job_dialog.close()
        invoice_dialog.close()

    def test_invoice_pdf(self):
        _job_id, invoice_id = self._seed_invoice()
        target = Path(self.tmp.name) / "invoice.pdf"
        generate_invoice_pdf(self.repo, invoice_id, target)
        self.assertTrue(target.exists())
        self.assertGreater(target.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
