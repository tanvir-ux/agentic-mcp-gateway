# Payments operations primer

This note is generic industry knowledge for a demo knowledge base. It is not a product manual.

## Payment lifecycle

A typical credit transfer moves through:

1. **Capture** — originator instructions accepted by the sending institution.
2. **Validation** — schema, sanctions screening, balance/limit checks.
3. **Clearing** — netting or gross settlement against a scheme (ACH-like, RTGS-like, or correspondent).
4. **Settlement** — final, irrevocable movement of funds (or a scheme equivalent).
5. **Notification** — confirmations to originator and beneficiary channels.

Statuses used in this demo store:

- `received` — accepted, not yet released
- `in_flight` — sent to a scheme or correspondent
- `settled` — completed
- `held` — waiting on compliance or repair
- `returned` — bounced with a reason code

## Investigation patterns

When a customer asks "where is my money":

- Search by `payment_id`, end-to-end reference, or account last-4.
- If status is `held`, check the hold reason (KYC mismatch, missing beneficiary BIC, dual-control pending).
- If status is `in_flight` beyond the scheme's SLA, open an ops ticket with the scheme reference.
- Never invent a settlement confirmation; cite the ledger row.

## Repair

Common repairs: wrong currency, truncated beneficiary name, invalid IBAN checksum, duplicate `end_to_end_id`. Duplicate detection should be idempotent on `(originator, end_to_end_id, amount, value_date)`.
