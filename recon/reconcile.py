"""Reconcile platform ledger vs bank settlements for one period and bridge the totals."""
import csv
from datetime import date, datetime
from decimal import Decimal as D

TOL = D("0.01")  # per-row tolerance: bank rounds to 2dp, so <=1 paisa is rounding, not an error

def _pd(r): return datetime.fromisoformat(r["timestamp"]).date()
def _sd(r): return date.fromisoformat(r["settled_date"])

def load(plat_path, bank_path):
    with open(plat_path, newline="") as f:
        plat = [{**r, "amount": D(r["amount"])} for r in csv.DictReader(f)]
    with open(bank_path, newline="") as f:
        bank = [{**r, "amount": D(r["amount"])} for r in csv.DictReader(f)]
    return plat, bank

def reconcile(plat, bank, start=date(2026, 10, 1), end=date(2026, 10, 31), tol=TOL):
    issues = []
    def issue(cat, ref, amt, detail):
        issues.append(dict(category=cat, reference=ref, amount=amt, detail=detail))

    in_p = [r for r in plat if start <= _pd(r) <= end]
    seen, uniq, dup_total = {}, [], D(0)
    for r in in_p:                                           # 1. duplicates first
        if r["txn_id"] in seen:
            dup_total += r["amount"]
            issue("duplicate", r["txn_id"], r["amount"], "txn_id appears more than once in platform ledger")
        else:
            seen[r["txn_id"]] = r; uniq.append(r)

    ids = {r["txn_id"] for r in plat}
    bank_by = {}
    for b in bank: bank_by.setdefault(b["reference"], []).append(b)
    bank_in = [b for b in bank if start <= _sd(b) <= end]
    bank_total = sum((b["amount"] for b in bank_in), D(0))

    used, timing, missing, mismatch, rounding, n_round = set(), D(0), D(0), D(0), D(0), 0
    for r in uniq:                                           # 2. match on reference
        bl = bank_by.get(r["txn_id"])
        if not bl:
            missing += r["amount"]
            issue("missing_settlement", r["txn_id"], r["amount"], "in platform ledger, no bank settlement found")
            continue
        b = bl[0]
        if _sd(b) > end:
            timing += r["amount"]
            issue("timing", r["txn_id"], r["amount"], f"settled {b['settled_date']}, after period end (not an error)")
        elif _sd(b) < start:
            missing += r["amount"]
            issue("missing_settlement", r["txn_id"], r["amount"], f"settled {b['settled_date']}, before period start")
        else:
            used.add(b["settlement_id"])
            diff = r["amount"] - b["amount"]
            if abs(diff) > tol:
                mismatch += diff
                issue("amount_mismatch", r["txn_id"], diff, f"platform {r['amount']} vs bank {b['amount']}")
            elif diff != 0:
                rounding += diff; n_round += 1

    for b in bank_in:                                        # 3. bank-side extras
        if b["settlement_id"] in used: continue
        dupe = b["reference"] in seen and b is not bank_by[b["reference"]][0]
        issue("bank_duplicate" if dupe else "unexpected_settlement", b["reference"], b["amount"],
              "bank settled this reference more than once" if dupe else "bank settlement with no platform transaction")
    unexpected = sum((b["amount"] for b in bank_in if b["settlement_id"] not in used), D(0))

    for r in uniq:                                           # 4. orphan refunds
        if r["type"] == "refund" and r["original_txn_id"] not in ids:
            issue("orphan_refund", r["txn_id"], r["amount"], f"original {r['original_txn_id']} not in ledger")

    if rounding != 0:                                        # 5. aggregate-only gap
        issue("rounding_drift", f"{n_round} rows", rounding,
              f"{n_round} rows each differ by <= {tol} but sum to {rounding}")

    plat_total = sum((r["amount"] for r in in_p), D(0))
    bridge = [("Platform ledger total (as recorded)", plat_total),
              ("Remove duplicate entries", -dup_total),
              ("Settles after period end (timing)", -timing),
              ("No bank settlement found", -missing),
              ("Amount mismatches > tolerance", -mismatch),
              ("Rounding drift (sub-cent, summed)", -rounding),
              ("Bank settlements not in ledger", unexpected)]
    computed = sum((a for _, a in bridge), D(0))
    return dict(issues=issues, bridge=bridge, platform_total=plat_total, bank_total=bank_total,
                gap=plat_total - bank_total, computed_bank_total=computed, residual=computed - bank_total)
