"""SQLite mock ledger + ticket desk. Seeded, not a real bank."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


SEED_PAYMENTS = [
    {
        "payment_id": "PMT-1001",
        "end_to_end_id": "INV-8841",
        "originator": "Northwind Traders",
        "beneficiary": "Contoso Ltd",
        "currency": "USD",
        "amount": 12500.00,
        "value_date": "2026-08-18",
        "status": "settled",
        "hold_reason": None,
        "scheme_ref": "UETR-aaa111",
    },
    {
        "payment_id": "PMT-1002",
        "end_to_end_id": "PO-5520",
        "originator": "Blue Harbor LLC",
        "beneficiary": "Harbor Supplies AG",
        "currency": "EUR",
        "amount": 8800.50,
        "value_date": "2026-08-20",
        "status": "held",
        "hold_reason": "kyc_review",
        "scheme_ref": "UETR-bbb222",
    },
    {
        "payment_id": "PMT-1003",
        "end_to_end_id": "SAL-091",
        "originator": "Cedar Payroll",
        "beneficiary": "A. Rivera",
        "currency": "USD",
        "amount": 3200.00,
        "value_date": "2026-08-21",
        "status": "in_flight",
        "hold_reason": None,
        "scheme_ref": "UETR-ccc333",
    },
    {
        "payment_id": "PMT-1004",
        "end_to_end_id": "INV-9012",
        "originator": "Maple Goods",
        "beneficiary": "Sahara Import Co",
        "currency": "USD",
        "amount": 45000.00,
        "value_date": "2026-08-19",
        "status": "returned",
        "hold_reason": "invalid_iban",
        "scheme_ref": "UETR-ddd444",
    },
]


@dataclass
class Ticket:
    ticket_id: str
    title: str
    queue: str
    related_payment_id: str | None
    body: str
    status: str


class OpsStore:
    def __init__(self, path: Path | str = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                end_to_end_id TEXT NOT NULL,
                originator TEXT NOT NULL,
                beneficiary TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount REAL NOT NULL,
                value_date TEXT NOT NULL,
                status TEXT NOT NULL,
                hold_reason TEXT,
                scheme_ref TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                queue TEXT NOT NULL,
                related_payment_id TEXT,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                created_on TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed(self) -> None:
        cur = self._conn.cursor()
        n = cur.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
        if n == 0:
            cur.executemany(
                """
                INSERT INTO payments (
                    payment_id, end_to_end_id, originator, beneficiary,
                    currency, amount, value_date, status, hold_reason, scheme_ref
                ) VALUES (
                    :payment_id, :end_to_end_id, :originator, :beneficiary,
                    :currency, :amount, :value_date, :status, :hold_reason, :scheme_ref
                )
                """,
                SEED_PAYMENTS,
            )
            self._conn.commit()

    def search_payments(
        self,
        payment_id: str | None = None,
        end_to_end_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if payment_id:
            clauses.append("payment_id = ?")
            params.append(payment_id)
        if end_to_end_id:
            clauses.append("end_to_end_id = ?")
            params.append(end_to_end_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if q:
            clauses.append(
                "(originator LIKE ? OR beneficiary LIKE ? OR scheme_ref LIKE ? OR payment_id LIKE ?)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, like])
        sql = "SELECT * FROM payments"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY value_date DESC, payment_id"
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def next_ticket_id(self) -> str:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM tickets"
        ).fetchone()
        return f"TCK-{1000 + int(row['c']) + 1}"

    def create_ticket(
        self,
        title: str,
        queue: str,
        body: str,
        related_payment_id: str | None = None,
    ) -> dict[str, Any]:
        ticket_id = self.next_ticket_id()
        payload = {
            "ticket_id": ticket_id,
            "title": title,
            "queue": queue,
            "related_payment_id": related_payment_id,
            "body": body,
            "status": "open",
            "created_on": date.today().isoformat(),
        }
        self._conn.execute(
            """
            INSERT INTO tickets (
                ticket_id, title, queue, related_payment_id, body, status, created_on
            ) VALUES (
                :ticket_id, :title, :queue, :related_payment_id, :body, :status, :created_on
            )
            """,
            payload,
        )
        self._conn.commit()
        return payload

    def list_tickets(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM tickets ORDER BY ticket_id").fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
