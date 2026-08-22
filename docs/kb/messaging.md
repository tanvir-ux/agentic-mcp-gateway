# Interbank messaging (SWIFT-like, generic)

Banks exchange structured messages for customer credit transfers, cover payments, and status requests. This demo uses SWIFT-like labels without claiming compatibility with any network.

## Message families (illustrative)

- **Customer credit** — originator-to-beneficiary with remittance info (historically MT103-like; ISO 20022 pacs.008 is the modern analogue).
- **Cover / bank-to-bank** — liquidity between correspondents (pacs.009 analogue).
- **Status / investigation** — camt.056 cancellation request, camt.029 resolution, pacs.002 status report.

## Fields investigators actually use

- `uetr` / tracking reference — correlate hops across correspondents.
- `end_to_end_id` — customer's own reference; keep it stable.
- `instructed_amount` vs `settled_amount` — FX or charges may explain a difference.
- `charge_bearer` — who pays scheme fees (OUR / SHA / BEN style).

## Status request playbook

1. Confirm the payment exists locally (`search_payments`).
2. If `in_flight`, note last hop timestamp; if older than the scheme SLA, `create_ticket` with queue `scheme_ops`.
3. If the customer wants a recall, ticket queue is `recalls` and the agent should retrieve the cancellation policy first.

Never paste full message blocks containing unmasked account numbers into chat logs.
