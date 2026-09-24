from __future__ import annotations

import unittest

from dokladnik.qr_payment import (
    build_spd,
    czech_account_to_iban,
    invoice_number_to_vs,
    validate_iban,
)


class QrPaymentTest(unittest.TestCase):
    def test_known_iban_is_valid(self):
        iban = "CZ9106000000000000000123"
        self.assertTrue(validate_iban(iban))

    def test_czech_account_converts_to_valid_iban(self):
        iban = czech_account_to_iban("123/0600")
        self.assertIsNotNone(iban)
        self.assertTrue(validate_iban(iban))

    def test_invoice_number_becomes_vs(self):
        self.assertEqual(invoice_number_to_vs("2026-001"), "2026001")

    def test_spd_payload(self):
        payload = build_spd(
            iban="CZ9106000000000000000123",
            amount_cents=45000,
            due_date="2026-10-08",
            invoice_number="2026-001",
        )
        self.assertTrue(payload.startswith("SPD*1.0*"))
        self.assertIn("ACC:CZ9106000000000000000123", payload)
        self.assertIn("AM:450.00", payload)
        self.assertIn("CC:CZK", payload)
        self.assertIn("DT:20261008", payload)
        self.assertIn("X-VS:2026001", payload)


if __name__ == "__main__":
    unittest.main()
