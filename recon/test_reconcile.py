from datetime import date
from decimal import Decimal as D
from generate_data import generate, next_bd
from reconcile import reconcile

def cats(res):
    out = {}
    for i in res["issues"]: out.setdefault(i["category"], []).append(i)
    return out

def P(i, ts, amt, typ="payment", orig=""):
    return dict(txn_id=i, timestamp=ts, type=typ, amount=D(amt), original_txn_id=orig)
def B(i, ref, d, amt):
    return dict(settlement_id=i, reference=ref, settled_date=d, amount=D(amt))

def test_finds_all_planted_gaps_and_nothing_else():
    plat, bank, truth = generate()
    c = cats(reconcile(plat, bank))
    assert set(c) == {"timing", "rounding_drift", "duplicate", "orphan_refund"}
    assert c["timing"][0]["reference"] == truth["timing"]["reference"]
    assert c["duplicate"][0]["reference"] == truth["duplicate"]["reference"]
    assert c["orphan_refund"][0]["reference"] == truth["orphan_refund"]["reference"]
    assert c["rounding_drift"][0]["amount"] == D(truth["rounding"]["drift"])

def test_bridge_ties_to_the_paisa():
    res = reconcile(*generate()[:2])
    assert res["residual"] == 0
    assert res["gap"] != 0                       # books really don't balance

def test_clean_data_has_zero_gaps():
    res = reconcile(*generate(plant=False)[:2])
    assert res["issues"] == [] and res["gap"] == 0

def test_deterministic_with_seed():
    assert generate(seed=7)[0] == generate(seed=7)[0]

def test_no_weekend_settlements():
    _, bank, _ = generate()
    from datetime import date as d
    assert all(d.fromisoformat(b["settled_date"]).weekday() < 5 for b in bank)

def test_friday_payment_settling_monday_is_not_flagged():
    assert next_bd(date(2026, 10, 9), 1) == date(2026, 10, 12)
    res = reconcile([P("T1", "2026-10-09T10:00", "50.00")], [B("S1", "T1", "2026-10-12", "50.00")])
    assert res["issues"] == [] and res["residual"] == 0

def test_empty_inputs():
    res = reconcile([], [])
    assert res["issues"] == [] and res["residual"] == 0

def test_two_legit_same_amount_payments_not_duplicates():
    plat = [P("T1", "2026-10-02T10:00", "99.00"), P("T2", "2026-10-02T10:00", "99.00")]
    bank = [B("S1", "T1", "2026-10-05", "99.00"), B("S2", "T2", "2026-10-05", "99.00")]
    assert reconcile(plat, bank)["issues"] == []

def test_same_id_twice_is_duplicate_and_bridge_ties():
    plat = [P("T1", "2026-10-02T10:00", "99.00"), P("T1", "2026-10-02T10:00", "99.00")]
    res = reconcile(plat, [B("S1", "T1", "2026-10-05", "99.00")])
    assert [i["category"] for i in res["issues"]] == ["duplicate"]
    assert res["gap"] == D("99.00") and res["residual"] == 0

def test_missing_unexpected_and_mismatch():
    plat = [P("T1", "2026-10-02T10:00", "10.00"), P("T2", "2026-10-02T10:00", "20.00")]
    bank = [B("S2", "T2", "2026-10-05", "18.00"), B("S9", "X9", "2026-10-06", "5.00")]
    res = reconcile(plat, bank)
    assert set(cats(res)) == {"missing_settlement", "amount_mismatch", "unexpected_settlement"}
    assert res["residual"] == 0

def test_refund_with_valid_original_not_orphan():
    plat = [P("T1", "2026-10-02T10:00", "10.00"), P("R1", "2026-10-03T10:00", "-10.00", "refund", "T1")]
    bank = [B("S1", "T1", "2026-10-05", "10.00"), B("S2", "R1", "2026-10-06", "-10.00")]
    assert reconcile(plat, bank)["issues"] == []
