from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 2


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._open()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            current = int(row["value"]) if row else 0

            if current < 1:
                self._migration_1(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '1')"
                )
                current = 1

            if current < 2:
                self._migration_2(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '2')"
                )
                current = 2

            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Databáze má novější schema ({current}) než program ({SCHEMA_VERSION})."
                )

    def _migration_1(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                company_name TEXT NOT NULL DEFAULT '',
                contact_person TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                billing_address TEXT NOT NULL DEFAULT '',
                ico TEXT NOT NULL DEFAULT '',
                dic TEXT NOT NULL DEFAULT '',
                activity_scope TEXT NOT NULL DEFAULT 'BOTH',
                favorite INTEGER NOT NULL DEFAULT 0,
                regular INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_date TEXT NOT NULL,
                activity TEXT NOT NULL CHECK(activity IN ('DDD','DOCISTA')),
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                customer_name TEXT NOT NULL DEFAULT '',
                service_address TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                service_summary TEXT NOT NULL DEFAULT '',
                price_cents INTEGER NOT NULL DEFAULT 0,
                tip_cents INTEGER NOT NULL DEFAULT 0,
                travel_cents INTEGER NOT NULL DEFAULT 0,
                distance_km REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'CASH',
                payment_status TEXT NOT NULL DEFAULT 'PAID',
                paid_at TEXT,
                document_type TEXT NOT NULL DEFAULT 'NONE',
                source TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                ddd_intervention_type TEXT NOT NULL DEFAULT '',
                ddd_pest TEXT NOT NULL DEFAULT '',
                ddd_protocol INTEGER NOT NULL DEFAULT 0,
                ddd_protocol_no TEXT NOT NULL DEFAULT '',
                ddd_stage TEXT NOT NULL DEFAULT '',
                ddd_next_visit TEXT,
                doc_cleaning_type TEXT NOT NULL DEFAULT '',
                doc_quantity REAL NOT NULL DEFAULT 0,
                doc_area_m2 REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL UNIQUE,
                job_id INTEGER UNIQUE REFERENCES jobs(id) ON DELETE SET NULL,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                buyer_name TEXT NOT NULL DEFAULT '',
                buyer_address TEXT NOT NULL DEFAULT '',
                buyer_ico TEXT NOT NULL DEFAULT '',
                buyer_dic TEXT NOT NULL DEFAULT '',
                payment_method TEXT NOT NULL DEFAULT 'BANK',
                payment_status TEXT NOT NULL DEFAULT 'UNPAID',
                paid_at TEXT,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                position INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT NOT NULL DEFAULT 'ks',
                unit_price_cents INTEGER NOT NULL DEFAULT 0,
                total_cents INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lookup_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(kind, value)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(job_date);
            CREATE INDEX IF NOT EXISTS idx_jobs_activity ON jobs(activity);
            CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
            CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices(issue_date);
            CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
            """
        )

        defaults = [
            ("customer_source", "Google vyhledávání", 10),
            ("customer_source", "Google reklama", 20),
            ("customer_source", "Seznam", 30),
            ("customer_source", "Facebook", 40),
            ("customer_source", "doporučení", 50),
            ("customer_source", "stálý zákazník", 60),
            ("customer_source", "web", 70),
            ("customer_source", "jiné", 80),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO lookup_values(kind, value, position)
            VALUES (?, ?, ?)
            """,
            defaults,
        )

        settings = {
            "seller_name": "",
            "seller_address": "",
            "seller_ico": "",
            "seller_dic": "",
            "seller_phone": "",
            "seller_email": "",
            "seller_bank_account": "",
            "invoice_due_days": "14",
            "invoice_number_digits": "3",
        }
        conn.executemany(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
            settings.items(),
        )

    def _migration_2(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()
        }
        if "qr_payment" not in columns:
            conn.execute(
                "ALTER TABLE invoices ADD COLUMN qr_payment INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES('seller_iban', '')"
        )

    def integrity_check(self) -> str:
        with self.connect() as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return str(row[0]) if row else "unknown"

    def backup_to(self, target: Path) -> None:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source:
            dest = sqlite3.connect(target)
            try:
                source.backup(dest)
            finally:
                dest.close()

    def schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            return int(row["value"]) if row else 0


def json_for_audit(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
