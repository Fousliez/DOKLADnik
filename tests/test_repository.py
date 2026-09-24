from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dokladnik.db import Database
from dokladnik.repository import Repository


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.sqlite3")
        self.db.initialize()
        self.repo = Repository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_client_job_dashboard_invoice_flow(self):
        client_id = self.repo.save_client(
            {
                "name": "Testovací klient",
                "company_name": "",
                "phone": "123456789",
                "email": "test@example.invalid",
                "address": "Testovací 1",
                "billing_address": "",
                "ico": "",
                "dic": "",
                "activity_scope": "BOTH",
                "favorite": True,
                "regular": True,
                "source": "doporučení",
                "note": "",
            }
        )

        job_id = self.repo.save_job(
            {
                "job_date": "2026-09-24",
                "activity": "DDD",
                "client_id": client_id,
                "customer_name": "Testovací klient",
                "service_address": "Testovací 1",
                "phone": "123456789",
                "email": "test@example.invalid",
                "service_summary": "Deratizace",
                "price_cents": 200000,
                "tip_cents": 10000,
                "travel_cents": 20000,
                "distance_km": 25,
                "payment_method": "CASH",
                "payment_status": "PAID",
                "paid_at": "2026-09-24",
                "document_type": "NONE",
                "source": "doporučení",
                "note": "",
                "ddd_intervention_type": "Deratizace",
                "ddd_pest": "myši",
                "ddd_protocol": True,
                "ddd_protocol_no": "P-1",
                "ddd_stage": "první",
                "ddd_next_visit": None,
                "doc_cleaning_type": "",
                "doc_quantity": 0,
                "doc_area_m2": 0,
            }
        )

        stats = self.repo.dashboard("DDD", "2026-01-01", "2026-12-31")
        self.assertEqual(stats["job_count"], 1)
        self.assertEqual(stats["revenue_cents"], 200000)
        self.assertEqual(stats["total_cents"], 230000)

        invoice_id = self.repo.create_invoice_from_job(job_id)
        invoice = self.repo.get_invoice(invoice_id)
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice["number"], "2026-001")
        self.assertEqual(invoice["total_cents"], 220000)

        job = self.repo.get_job(job_id)
        self.assertEqual(job["document_type"], "INVOICE")
        self.assertEqual(job["invoice_number"], "2026-001")

        audits = self.repo.recent_audit()
        self.assertGreaterEqual(len(audits), 3)

    def test_soft_delete_keeps_data_out_of_normal_lists(self):
        client_id = self.repo.save_client({"name": "Ke smazání"})
        self.assertTrue(any(x["id"] == client_id for x in self.repo.list_clients()))
        self.repo.soft_delete_client(client_id)
        self.assertFalse(any(x["id"] == client_id for x in self.repo.list_clients()))
        self.assertTrue(any(x["id"] == client_id for x in self.repo.list_clients(include_deleted=True)))

    def test_invoice_can_be_safely_assigned_to_job(self):
        first_job = self.repo.save_job(
            {
                "job_date": "2026-09-24",
                "activity": "DDD",
                "customer_name": "První",
                "service_summary": "Test",
            }
        )
        second_job = self.repo.save_job(
            {
                "job_date": "2026-09-24",
                "activity": "DOCISTA",
                "customer_name": "Druhý",
                "service_summary": "Test",
            }
        )
        invoice_id = self.repo.create_invoice_from_job(first_job)

        with self.assertRaises(ValueError):
            self.repo.assign_invoice_to_job(second_job, invoice_id)

        self.repo.assign_invoice_to_job(first_job, None)
        available = self.repo.list_assignable_invoices(second_job)
        self.assertTrue(any(row["id"] == invoice_id for row in available))

        self.repo.assign_invoice_to_job(second_job, invoice_id)
        invoice = self.repo.get_invoice(invoice_id)
        self.assertEqual(invoice["job_id"], second_job)


if __name__ == "__main__":
    unittest.main()
