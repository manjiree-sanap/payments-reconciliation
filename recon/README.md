# Payments reconciliation (Onelab AI Fitness Assessment)

Run: `pip install -r requirements.txt && python generate_data.py && streamlit run app.py`
Tests: `pytest -q`

## What it does
Generates a synthetic October 2026 platform ledger and bank settlement file, plants 4 gaps, reconciles them,
and builds a bridge from platform total to bank total that ties to the paisa.

| Planted gap | How it is detected |
|---|---|
| Txn on 30 Oct settling 2 Nov | Bank row dated after period end -> `timing` (not an error) |
| Rounding visible only when summed | 200 rows differ by 0.005 each (within tolerance, so row-matches) -> `rounding_drift` of 1.00 on the total |
| Duplicate in platform ledger | Same `txn_id` twice -> `duplicate`, removed before matching |
| Refund with no original | `original_txn_id` absent from ledger -> `orphan_refund` |

## Assumptions
1. INR, single currency; amounts are gross (bank fees settled separately).
2. Period is 1-31 Oct 2026; platform records instantly, bank settles 1-2 business days later (no weekend settlement).
3. Match key is `txn_id` = bank `reference`. One bank line per transaction.
4. Platform computes amounts to 3 decimals; bank rounds to 2 dp half-up. Per-row tolerance is 0.01.
5. Refunds are full, negative, and settle through the bank like payments. The orphan refund did settle at the bank.
6. Bank file contains rows dated after month end (the November settlement); rows dated before the period start are not modelled.

## What it would get wrong in production
It matches on exact IDs, so banks that truncate or reformat references would turn real matches into false "missing" and "unexpected" gaps. It assumes one currency, fixed business-day lags and no holidays, so FX, partial settlements and chargebacks would create noise. Real acquirers also settle many transactions in one batched line net of fees, which a 1:1 matcher cannot reconcile without a batch-to-transaction mapping.
