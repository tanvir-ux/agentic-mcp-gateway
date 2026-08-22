# KYC and screening (high level)

Know Your Customer (KYC) and ongoing monitoring are separate from payment rails but they gate them.

## Onboarding

- Collect legal identity, ownership (UBO) for corporates, and purpose of account.
- Risk-rate the customer (low / medium / high). High-risk names require enhanced due diligence.
- Screening lists are typically sanctions, PEP, and adverse media. Hits must be dispositioned by a human; an agent may **flag**, not **clear**.

## Payment-time checks

Before release:

- Name/address vs beneficiary profile (fuzzy match — false positives are expected).
- Jurisdiction of beneficiary bank vs restricted-country list.
- Velocity: many small credits to a new beneficiary can be as suspicious as one large credit.

## Agent rules of engagement

- If a payment is `held` for `kyc_review`, retrieve the policy snippet and create a ticket for the KYC queue.
- Do not recommend bypassing screening.
- Do not store full government ID numbers in ticket descriptions; use last-4 or an internal party id.
