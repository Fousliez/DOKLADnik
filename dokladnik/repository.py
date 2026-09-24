from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .db import Database, json_for_audit, now_iso


CLIENT_FIELDS = [
    "name", "company_name", "contact_person", "phone", "email", "address",
    "billing_address", "ico", "dic", "activity_scope", "favorite", "regular",
    "source", "note",
]

JOB_FIELDS = [
    "job_date", "activity", "client_id", "customer_name", "service_address",
    "phone", "email", "service_summary", "price_cents", "tip_cents",
    "travel_cents", "distance_km", "payment_method", "payment_status",
    "paid_at", "document_type", "source", "note", "ddd_intervention_type",
    "ddd_pest", "ddd_protocol", "ddd_protocol_no", "ddd_stage",
    "ddd_next_visit", "doc_cleaning_type", "doc_quantity", "doc_area_m2",
]

INVOICE_FIELDS = [
    "number", "issue_date", "due_date", "buyer_name", "buyer_address",
    "buyer_ico", "buyer_dic", "payment_method", "payment_status", "paid_at",
    "note",
]


def row_dict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, db: Database):
        self.db = db

    def _audit(
        self,
        conn,
        entity_type: str,
        entity_id: int,
        action: str,
        before: dict | None,
        after: dict | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log(entity_type, entity_id, action, before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                action,
                json_for_audit(before),
                json_for_audit(after),
                now_iso(),
            ),
        )

    # ---------- Settings / lookups ----------

    def get_setting(self, key: str, default: str = "") -> str:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,)
            ).fetchone()
            return str(row["value"]) if row else default

    def get_settings(self) -> dict[str, str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM app_settings ORDER BY key"
            ).fetchall()
            return {str(r["key"]): str(r["value"]) for r in rows}

    def save_settings(self, values: dict[str, str]) -> None:
        with self.db.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO app_settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                [(str(k), str(v)) for k, v in values.items()],
            )

    def list_lookup(self, kind: str) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT value FROM lookup_values
                WHERE kind=? AND active=1
                ORDER BY position, value COLLATE NOCASE
                """,
                (kind,),
            ).fetchall()
            return [str(r["value"]) for r in rows]

    def add_lookup_value(self, kind: str, value: str) -> None:
        value = value.strip()
        if not value:
            return
        with self.db.transaction() as conn:
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 10 FROM lookup_values WHERE kind=?",
                (kind,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT OR IGNORE INTO lookup_values(kind, value, position, active)
                VALUES (?, ?, ?, 1)
                """,
                (kind, value, pos),
            )

    # ---------- Clients ----------

    def get_client(self, client_id: int) -> dict | None:
        with self.db.connect() as conn:
            return row_dict(
                conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            )

    def list_clients(self, search: str = "", include_deleted: bool = False) -> list[dict]:
        where = ["1=1"]
        params: list[Any] = []
        if not include_deleted:
            where.append("c.deleted_at IS NULL")
        if search.strip():
            token = f"%{search.strip()}%"
            where.append(
                """(
                    c.name LIKE ? OR c.company_name LIKE ? OR c.contact_person LIKE ?
                    OR c.phone LIKE ? OR c.email LIKE ? OR c.address LIKE ?
                    OR c.ico LIKE ? OR c.source LIKE ?
                )"""
            )
            params.extend([token] * 8)

        sql = f"""
            SELECT
                c.*,
                COUNT(j.id) AS job_count,
                COALESCE(SUM(j.price_cents + j.tip_cents + j.travel_cents), 0) AS spent_cents,
                MAX(j.job_date) AS last_job_date
            FROM clients c
            LEFT JOIN jobs j ON j.client_id=c.id AND j.deleted_at IS NULL
            WHERE {' AND '.join(where)}
            GROUP BY c.id
            ORDER BY c.favorite DESC, c.regular DESC,
                     COALESCE(NULLIF(c.company_name,''), c.name) COLLATE NOCASE
        """
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def save_client(self, data: dict, client_id: int | None = None) -> int:
        values = {k: data.get(k) for k in CLIENT_FIELDS}
        values["name"] = (values.get("name") or "").strip()
        values["company_name"] = (values.get("company_name") or "").strip()
        if not values["name"] and not values["company_name"]:
            raise ValueError("Klient musí mít jméno nebo název firmy.")
        values["favorite"] = int(bool(values.get("favorite")))
        values["regular"] = int(bool(values.get("regular")))
        values["activity_scope"] = values.get("activity_scope") or "BOTH"
        for key in CLIENT_FIELDS:
            if values[key] is None:
                values[key] = ""

        with self.db.transaction() as conn:
            stamp = now_iso()
            if client_id is None:
                columns = ", ".join(CLIENT_FIELDS + ["created_at", "updated_at"])
                placeholders = ", ".join(["?"] * (len(CLIENT_FIELDS) + 2))
                cur = conn.execute(
                    f"INSERT INTO clients({columns}) VALUES ({placeholders})",
                    [values[k] for k in CLIENT_FIELDS] + [stamp, stamp],
                )
                client_id = int(cur.lastrowid)
                after = row_dict(
                    conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
                )
                self._audit(conn, "client", client_id, "CREATE", None, after)
            else:
                before = row_dict(
                    conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
                )
                if before is None:
                    raise KeyError(f"Klient {client_id} neexistuje.")
                changed = any(before.get(k) != values[k] for k in CLIENT_FIELDS)
                if changed:
                    assignments = ", ".join(f"{k}=?" for k in CLIENT_FIELDS)
                    conn.execute(
                        f"UPDATE clients SET {assignments}, updated_at=? WHERE id=?",
                        [values[k] for k in CLIENT_FIELDS] + [stamp, client_id],
                    )
                    after = row_dict(
                        conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
                    )
                    self._audit(conn, "client", client_id, "UPDATE", before, after)
        return client_id

    def soft_delete_client(self, client_id: int) -> None:
        with self.db.transaction() as conn:
            before = row_dict(
                conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            )
            if not before or before.get("deleted_at"):
                return
            stamp = now_iso()
            conn.execute(
                "UPDATE clients SET deleted_at=?, updated_at=? WHERE id=?",
                (stamp, stamp, client_id),
            )
            after = row_dict(
                conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            )
            self._audit(conn, "client", client_id, "DELETE", before, after)

    # ---------- Jobs ----------

    def get_job(self, job_id: int) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT j.*, i.id AS invoice_id, COALESCE(i.number,'') AS invoice_number
                FROM jobs j
                LEFT JOIN invoices i ON i.job_id=j.id AND i.deleted_at IS NULL
                WHERE j.id=?
                """,
                (job_id,),
            ).fetchone()
            return row_dict(row)

    def list_jobs(
        self,
        activity: str = "ALL",
        from_date: str | None = None,
        to_date: str | None = None,
        search: str = "",
        include_deleted: bool = False,
    ) -> list[dict]:
        where = ["1=1"]
        params: list[Any] = []
        if not include_deleted:
            where.append("j.deleted_at IS NULL")
        if activity in {"DDD", "DOCISTA"}:
            where.append("j.activity=?")
            params.append(activity)
        if from_date:
            where.append("j.job_date>=?")
            params.append(from_date)
        if to_date:
            where.append("j.job_date<=?")
            params.append(to_date)
        if search.strip():
            token = f"%{search.strip()}%"
            where.append(
                """(
                    j.customer_name LIKE ? OR j.service_address LIKE ? OR j.phone LIKE ?
                    OR j.email LIKE ? OR j.service_summary LIKE ? OR j.source LIKE ?
                    OR j.ddd_pest LIKE ? OR j.ddd_protocol_no LIKE ?
                    OR COALESCE(i.number,'') LIKE ?
                )"""
            )
            params.extend([token] * 9)

        sql = f"""
            SELECT
                j.*,
                COALESCE(i.number,'') AS invoice_number,
                i.id AS invoice_id,
                (j.price_cents + j.tip_cents + j.travel_cents) AS total_cents
            FROM jobs j
            LEFT JOIN invoices i ON i.job_id=j.id AND i.deleted_at IS NULL
            WHERE {' AND '.join(where)}
            ORDER BY j.job_date DESC, j.id DESC
        """
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def save_job(self, data: dict, job_id: int | None = None) -> int:
        values = {k: data.get(k) for k in JOB_FIELDS}
        values["job_date"] = values.get("job_date") or date.today().isoformat()
        values["activity"] = values.get("activity") or "DDD"
        if values["activity"] not in {"DDD", "DOCISTA"}:
            raise ValueError("Neplatná činnost.")
        values["client_id"] = values.get("client_id") or None
        values["price_cents"] = int(values.get("price_cents") or 0)
        values["tip_cents"] = int(values.get("tip_cents") or 0)
        values["travel_cents"] = int(values.get("travel_cents") or 0)
        values["distance_km"] = float(values.get("distance_km") or 0)
        values["ddd_protocol"] = int(bool(values.get("ddd_protocol")))
        values["doc_quantity"] = float(values.get("doc_quantity") or 0)
        values["doc_area_m2"] = float(values.get("doc_area_m2") or 0)
        values["payment_method"] = values.get("payment_method") or "CASH"
        values["payment_status"] = values.get("payment_status") or "PAID"
        values["document_type"] = values.get("document_type") or "NONE"

        nullable = {"client_id", "paid_at", "ddd_next_visit"}
        for key in JOB_FIELDS:
            if key not in nullable and values[key] is None:
                values[key] = ""

        if values["payment_status"] == "PAID" and not values.get("paid_at"):
            values["paid_at"] = values["job_date"]
        if values["payment_status"] != "PAID":
            values["paid_at"] = values.get("paid_at") or None

        with self.db.transaction() as conn:
            stamp = now_iso()
            if job_id is None:
                columns = ", ".join(JOB_FIELDS + ["created_at", "updated_at"])
                placeholders = ", ".join(["?"] * (len(JOB_FIELDS) + 2))
                cur = conn.execute(
                    f"INSERT INTO jobs({columns}) VALUES ({placeholders})",
                    [values[k] for k in JOB_FIELDS] + [stamp, stamp],
                )
                job_id = int(cur.lastrowid)
                after = row_dict(
                    conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                )
                self._audit(conn, "job", job_id, "CREATE", None, after)
            else:
                before = row_dict(
                    conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                )
                if before is None:
                    raise KeyError(f"Zakázka {job_id} neexistuje.")
                changed = any(before.get(k) != values[k] for k in JOB_FIELDS)
                if changed:
                    assignments = ", ".join(f"{k}=?" for k in JOB_FIELDS)
                    conn.execute(
                        f"UPDATE jobs SET {assignments}, updated_at=? WHERE id=?",
                        [values[k] for k in JOB_FIELDS] + [stamp, job_id],
                    )
                    after = row_dict(
                        conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
                    )
                    self._audit(conn, "job", job_id, "UPDATE", before, after)
        return job_id

    def soft_delete_job(self, job_id: int) -> None:
        with self.db.transaction() as conn:
            before = row_dict(
                conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            )
            if not before or before.get("deleted_at"):
                return
            stamp = now_iso()
            conn.execute(
                "UPDATE jobs SET deleted_at=?, updated_at=? WHERE id=?",
                (stamp, stamp, job_id),
            )
            after = row_dict(
                conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            )
            self._audit(conn, "job", job_id, "DELETE", before, after)

    def dashboard(
        self,
        activity: str = "ALL",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, int | float]:
        where = ["j.deleted_at IS NULL"]
        params: list[Any] = []
        if activity in {"DDD", "DOCISTA"}:
            where.append("j.activity=?")
            params.append(activity)
        if from_date:
            where.append("j.job_date>=?")
            params.append(from_date)
        if to_date:
            where.append("j.job_date<=?")
            params.append(to_date)

        where_sql = " AND ".join(where)
        sql = f"""
            SELECT
                COUNT(*) AS job_count,
                COALESCE(SUM(j.price_cents),0) AS revenue_cents,
                COALESCE(SUM(j.tip_cents),0) AS tips_cents,
                COALESCE(SUM(j.travel_cents),0) AS travel_cents,
                COALESCE(SUM(j.price_cents+j.tip_cents+j.travel_cents),0) AS total_cents,
                COALESCE(SUM(CASE WHEN j.payment_status!='PAID'
                    THEN j.price_cents+j.tip_cents+j.travel_cents ELSE 0 END),0) AS unpaid_cents,
                COALESCE(SUM(j.distance_km),0) AS distance_km
            FROM jobs j
            WHERE {where_sql}
        """
        with self.db.connect() as conn:
            result = dict(conn.execute(sql, params).fetchone())
            invoice_sql = f"""
                SELECT COUNT(i.id)
                FROM invoices i
                JOIN jobs j ON j.id=i.job_id
                WHERE i.deleted_at IS NULL AND {where_sql}
            """
            result["invoice_count"] = int(conn.execute(invoice_sql, params).fetchone()[0])
            count = int(result["job_count"])
            result["average_cents"] = int(result["total_cents"] / count) if count else 0
            return result

    def payment_breakdown(
        self,
        activity: str = "ALL",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        where = ["deleted_at IS NULL"]
        params: list[Any] = []
        if activity in {"DDD", "DOCISTA"}:
            where.append("activity=?")
            params.append(activity)
        if from_date:
            where.append("job_date>=?")
            params.append(from_date)
        if to_date:
            where.append("job_date<=?")
            params.append(to_date)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payment_method,
                       COUNT(*) AS job_count,
                       SUM(price_cents+tip_cents+travel_cents) AS total_cents
                FROM jobs
                WHERE {' AND '.join(where)}
                GROUP BY payment_method
                ORDER BY total_cents DESC
                """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def source_breakdown(
        self,
        activity: str = "ALL",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        where = ["deleted_at IS NULL"]
        params: list[Any] = []
        if activity in {"DDD", "DOCISTA"}:
            where.append("activity=?")
            params.append(activity)
        if from_date:
            where.append("job_date>=?")
            params.append(from_date)
        if to_date:
            where.append("job_date<=?")
            params.append(to_date)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT CASE WHEN TRIM(source)='' THEN '(neuvedeno)' ELSE source END AS source_name,
                       COUNT(*) AS job_count,
                       SUM(price_cents+tip_cents+travel_cents) AS total_cents
                FROM jobs
                WHERE {' AND '.join(where)}
                GROUP BY source_name
                ORDER BY total_cents DESC
                """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------- Invoices ----------

    def next_invoice_number(self, year: int, conn=None) -> str:
        own = conn is None
        if own:
            conn = self.db._open()
        try:
            rows = conn.execute(
                "SELECT number FROM invoices WHERE number LIKE ?",
                (f"{year}-%",),
            ).fetchall()
            maximum = 0
            for row in rows:
                try:
                    suffix = str(row["number"]).split("-", 1)[1]
                    maximum = max(maximum, int(suffix))
                except (ValueError, IndexError):
                    continue
            try:
                digits = int(
                    conn.execute(
                        "SELECT value FROM app_settings WHERE key='invoice_number_digits'"
                    ).fetchone()[0]
                )
            except Exception:
                digits = 3
            return f"{year}-{maximum + 1:0{max(1, digits)}d}"
        finally:
            if own:
                conn.close()

    def create_invoice_from_job(self, job_id: int) -> int:
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM invoices WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing and existing["deleted_at"] is None:
                return int(existing["id"])

            job_row = conn.execute(
                "SELECT * FROM jobs WHERE id=? AND deleted_at IS NULL", (job_id,)
            ).fetchone()
            if not job_row:
                raise KeyError("Zakázka neexistuje.")
            job = dict(job_row)

            client = None
            if job.get("client_id"):
                row = conn.execute(
                    "SELECT * FROM clients WHERE id=?", (job["client_id"],)
                ).fetchone()
                client = dict(row) if row else None

            today = date.today()
            due_row = conn.execute(
                "SELECT value FROM app_settings WHERE key='invoice_due_days'"
            ).fetchone()
            try:
                due_days = int(due_row[0]) if due_row else 14
            except ValueError:
                due_days = 14

            buyer_name = ""
            buyer_address = ""
            buyer_ico = ""
            buyer_dic = ""
            if client:
                buyer_name = client.get("company_name") or client.get("name") or ""
                buyer_address = client.get("billing_address") or client.get("address") or ""
                buyer_ico = client.get("ico") or ""
                buyer_dic = client.get("dic") or ""
            buyer_name = buyer_name or job.get("customer_name") or ""
            buyer_address = buyer_address or job.get("service_address") or ""

            number = self.next_invoice_number(today.year, conn)
            amount = int(job.get("price_cents") or 0) + int(job.get("travel_cents") or 0)
            stamp = now_iso()
            status = job.get("payment_status") or "UNPAID"
            paid_at = job.get("paid_at") if status == "PAID" else None

            if existing:
                invoice_id = int(existing["id"])
                conn.execute(
                    """
                    UPDATE invoices SET
                        number=?, client_id=?, issue_date=?, due_date=?, buyer_name=?,
                        buyer_address=?, buyer_ico=?, buyer_dic=?, payment_method=?,
                        payment_status=?, paid_at=?, note='', updated_at=?, deleted_at=NULL
                    WHERE id=?
                    """,
                    (
                        number, job.get("client_id"), today.isoformat(),
                        (today + timedelta(days=due_days)).isoformat(),
                        buyer_name, buyer_address, buyer_ico, buyer_dic,
                        job.get("payment_method") or "BANK", status, paid_at, stamp,
                        invoice_id,
                    ),
                )
                conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
            else:
                cur = conn.execute(
                    """
                    INSERT INTO invoices(
                        number, job_id, client_id, issue_date, due_date, buyer_name,
                        buyer_address, buyer_ico, buyer_dic, payment_method,
                        payment_status, paid_at, note, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        number, job_id, job.get("client_id"), today.isoformat(),
                        (today + timedelta(days=due_days)).isoformat(),
                        buyer_name, buyer_address, buyer_ico, buyer_dic,
                        job.get("payment_method") or "BANK", status, paid_at, "",
                        stamp, stamp,
                    ),
                )
                invoice_id = int(cur.lastrowid)

            description = job.get("service_summary") or (
                "DDD služby" if job.get("activity") == "DDD" else "Čištění"
            )
            conn.execute(
                """
                INSERT INTO invoice_items(
                    invoice_id, position, description, quantity, unit,
                    unit_price_cents, total_cents
                ) VALUES (?, 10, ?, 1, 'ks', ?, ?)
                """,
                (invoice_id, description, amount, amount),
            )

            invoice_after = row_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            self._audit(
                conn, "invoice", invoice_id,
                "RESTORE" if existing else "CREATE",
                dict(existing) if existing else None,
                invoice_after,
            )

            before_job = dict(job)
            conn.execute(
                "UPDATE jobs SET document_type='INVOICE', updated_at=? WHERE id=?",
                (stamp, job_id),
            )
            after_job = row_dict(
                conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            )
            if before_job.get("document_type") != "INVOICE":
                self._audit(conn, "job", job_id, "UPDATE", before_job, after_job)
            return invoice_id

    def get_invoice(self, invoice_id: int) -> dict | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT i.*, COALESCE(SUM(ii.total_cents),0) AS total_cents,
                       j.activity, j.customer_name, j.service_summary
                FROM invoices i
                LEFT JOIN invoice_items ii ON ii.invoice_id=i.id
                LEFT JOIN jobs j ON j.id=i.job_id
                WHERE i.id=?
                GROUP BY i.id
                """,
                (invoice_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["items"] = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM invoice_items
                    WHERE invoice_id=?
                    ORDER BY position, id
                    """,
                    (invoice_id,),
                ).fetchall()
            ]
            return result

    def list_invoices(
        self, activity: str = "ALL", search: str = "", include_deleted: bool = False
    ) -> list[dict]:
        where = ["1=1"]
        params: list[Any] = []
        if not include_deleted:
            where.append("i.deleted_at IS NULL")
        if activity in {"DDD", "DOCISTA"}:
            where.append("j.activity=?")
            params.append(activity)
        if search.strip():
            token = f"%{search.strip()}%"
            where.append(
                """(
                    i.number LIKE ? OR i.buyer_name LIKE ? OR i.buyer_address LIKE ?
                    OR i.buyer_ico LIKE ? OR COALESCE(j.customer_name,'') LIKE ?
                )"""
            )
            params.extend([token] * 5)
        sql = f"""
            SELECT i.*, j.activity, j.customer_name,
                   COALESCE(SUM(ii.total_cents),0) AS total_cents
            FROM invoices i
            LEFT JOIN jobs j ON j.id=i.job_id
            LEFT JOIN invoice_items ii ON ii.invoice_id=i.id
            WHERE {' AND '.join(where)}
            GROUP BY i.id
            ORDER BY i.issue_date DESC, i.id DESC
        """
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def save_invoice(self, invoice_id: int, data: dict, items: list[dict]) -> None:
        if not items:
            raise ValueError("Faktura musí mít alespoň jednu položku.")
        values = {k: data.get(k) for k in INVOICE_FIELDS}
        for key in INVOICE_FIELDS:
            if values[key] is None:
                values[key] = ""
        if not str(values["number"]).strip():
            raise ValueError("Faktura musí mít číslo.")

        with self.db.transaction() as conn:
            before = row_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            if not before:
                raise KeyError("Faktura neexistuje.")
            assignments = ", ".join(f"{k}=?" for k in INVOICE_FIELDS)
            conn.execute(
                f"UPDATE invoices SET {assignments}, updated_at=? WHERE id=?",
                [values[k] for k in INVOICE_FIELDS] + [now_iso(), invoice_id],
            )
            conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
            for pos, item in enumerate(items, start=1):
                quantity = float(item.get("quantity") or 1)
                unit_price = int(item.get("unit_price_cents") or 0)
                total = int(round(quantity * unit_price))
                conn.execute(
                    """
                    INSERT INTO invoice_items(
                        invoice_id, position, description, quantity, unit,
                        unit_price_cents, total_cents
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id, pos * 10, str(item.get("description") or ""),
                        quantity, str(item.get("unit") or "ks"), unit_price, total,
                    ),
                )
            after = row_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            if before != after:
                self._audit(conn, "invoice", invoice_id, "UPDATE", before, after)

            if after.get("job_id"):
                paid_at = after.get("paid_at") if after.get("payment_status") == "PAID" else None
                conn.execute(
                    """
                    UPDATE jobs SET payment_method=?, payment_status=?, paid_at=?,
                                    document_type='INVOICE', updated_at=?
                    WHERE id=?
                    """,
                    (
                        after.get("payment_method") or "BANK",
                        after.get("payment_status") or "UNPAID",
                        paid_at, now_iso(), after["job_id"],
                    ),
                )

    def soft_delete_invoice(self, invoice_id: int) -> None:
        with self.db.transaction() as conn:
            before = row_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            if not before or before.get("deleted_at"):
                return
            stamp = now_iso()
            conn.execute(
                "UPDATE invoices SET deleted_at=?, updated_at=? WHERE id=?",
                (stamp, stamp, invoice_id),
            )
            if before.get("job_id"):
                conn.execute(
                    """
                    UPDATE jobs
                    SET document_type='NONE', updated_at=?
                    WHERE id=? AND document_type='INVOICE'
                    """,
                    (stamp, before["job_id"]),
                )
            after = row_dict(
                conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            )
            self._audit(conn, "invoice", invoice_id, "DELETE", before, after)

    # ---------- Audit ----------

    def recent_audit(self, limit: int = 100) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            return [dict(r) for r in rows]
