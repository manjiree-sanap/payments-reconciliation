"""Synthetic October-2026 platform ledger + bank settlement file with 4 planted gaps."""
import csv, json, random
from datetime import date, datetime, timedelta
from decimal import Decimal as D, ROUND_HALF_UP

def q2(x): return x.quantize(D("0.01"), ROUND_HALF_UP)
def fmt(x): return format(x, "f")

def next_bd(d, n):
    """Date n business days after d (Sat/Sun skipped)."""
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d

def generate(seed=42, n=500, plant=True):
    rng = random.Random(seed)
    plat, bank, truth = [], [], {}
    rounded = set(rng.sample(range(1, n), 200)) if plant else set()
    pays = {}
    for i in range(1, n + 1):
        d = date(2026, 10, 1) + timedelta(days=rng.randint(0, 27))
        ts = datetime(d.year, d.month, d.day, rng.randint(0, 23), rng.randint(0, 59))
        amt = D(rng.randint(100, 500000)) / 100
        lag = rng.randint(1, 2)
        if plant and i == n:                      # GAP 1: settles next month
            ts, amt, lag = datetime(2026, 10, 30, 14, 22), D("4250.00"), 1
        if i in rounded:                          # GAP 2: 3-dp platform amount, bank rounds to 2dp
            amt += D("0.005")
        pays[i] = dict(txn_id=f"TXN-{i:04d}", ts=ts, amt=amt, lag=lag)
        plat.append(dict(txn_id=f"TXN-{i:04d}", timestamp=ts.isoformat(), type="payment",
                         amount=amt, original_txn_id=""))
        bank.append(dict(reference=f"TXN-{i:04d}", settled_date=next_bd(ts.date(), lag).isoformat(),
                         amount=q2(amt)))
    if plant:
        truth["timing"] = dict(reference=f"TXN-{n:04d}", amount=fmt(D("4250.00")), settled="2026-11-02")
        truth["rounding"] = dict(rows=200, drift=fmt(D("-0.005") * 200))  # platform minus bank
    # valid refunds
    clean = [i for i in pays if i not in rounded and i != n]
    for k, i in enumerate(rng.sample(clean, 12), 1):
        p = pays[i]
        ts = min(p["ts"] + timedelta(days=rng.randint(1, 3)), datetime(2026, 10, 27, 11, 0))
        plat.append(dict(txn_id=f"RFD-{k:04d}", timestamp=ts.isoformat(), type="refund",
                         amount=-p["amt"], original_txn_id=p["txn_id"]))
        bank.append(dict(reference=f"RFD-{k:04d}", settled_date=next_bd(ts.date(), rng.randint(1, 2)).isoformat(),
                         amount=-p["amt"]))
    if plant:
        dup_i = rng.choice([i for i in clean if i not in {r for r in []}])
        dup_row = next(r for r in plat if r["txn_id"] == f"TXN-{dup_i:04d}")
        plat.append(dict(dup_row))                # GAP 3: duplicate in platform ledger
        truth["duplicate"] = dict(reference=dup_row["txn_id"], amount=fmt(dup_row["amount"]))
        ts = datetime(2026, 10, 20, 16, 5)        # GAP 4: refund with no original
        plat.append(dict(txn_id="RFD-0013", timestamp=ts.isoformat(), type="refund",
                         amount=D("-75.50"), original_txn_id="TXN-90001"))
        bank.append(dict(reference="RFD-0013", settled_date=next_bd(ts.date(), 1).isoformat(),
                         amount=D("-75.50")))
        truth["orphan_refund"] = dict(reference="RFD-0013", original="TXN-90001", amount="-75.50")
    plat.sort(key=lambda r: r["timestamp"])
    bank.sort(key=lambda r: r["settled_date"])
    for k, b in enumerate(bank, 1):
        b["settlement_id"] = f"STL-{k:05d}"
    return plat, bank, truth

def write_csv(plat, bank, truth, outdir="data"):
    import os
    os.makedirs(outdir, exist_ok=True)
    with open(f"{outdir}/platform_ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["txn_id", "timestamp", "type", "amount", "original_txn_id"]); w.writeheader()
        for r in plat: w.writerow({**r, "amount": fmt(r["amount"])})
    with open(f"{outdir}/bank_settlements.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["settlement_id", "reference", "settled_date", "amount"]); w.writeheader()
        for r in bank: w.writerow({**r, "amount": fmt(r["amount"])})
    with open(f"{outdir}/ground_truth.json", "w") as f:
        json.dump(truth, f, indent=2)

if __name__ == "__main__":
    write_csv(*generate())
    print("wrote data/")
