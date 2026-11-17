import json, pandas as pd, streamlit as st
from generate_data import generate, write_csv
from reconcile import reconcile, load

st.set_page_config(page_title="Payments Reconciliation", layout="wide")
st.title("Month-end payments reconciliation")
st.caption("Platform ledger vs bank settlements, October 2026")

src = st.sidebar.radio("Data", ["Generate synthetic data", "Upload CSVs"])
truth = None
if src == "Generate synthetic data":
    seed = st.sidebar.number_input("Seed", value=42, step=1)
    plat, bank, truth = generate(seed=int(seed))
else:
    pf = st.sidebar.file_uploader("platform_ledger.csv"); bf = st.sidebar.file_uploader("bank_settlements.csv")
    if not (pf and bf): st.info("Upload both files."); st.stop()
    open("/tmp/p.csv", "wb").write(pf.read()); open("/tmp/b.csv", "wb").write(bf.read())
    plat, bank = load("/tmp/p.csv", "/tmp/b.csv")

res = reconcile(plat, bank)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Platform total", f"{res['platform_total']:,.2f}"); c2.metric("Bank total", f"{res['bank_total']:,.2f}")
c3.metric("Gap", f"{res['gap']:,.2f}"); c4.metric("Unexplained", f"{res['residual']:,.2f}")

st.subheader("Bridge: platform total to bank total")
bridge = pd.DataFrame([(l, float(a)) for l, a in res["bridge"]], columns=["Step", "Amount"])
bridge.loc[len(bridge)] = ["= Bank total (computed)", float(res["computed_bank_total"])]
st.dataframe(bridge, hide_index=True, use_container_width=True)

st.subheader("Gaps found")
iss = pd.DataFrame(res["issues"])
if iss.empty: st.success("No gaps. Books balance.")
else:
    iss["amount"] = iss["amount"].astype(float)
    st.bar_chart(iss.groupby("category")["amount"].sum())
    st.dataframe(iss, hide_index=True, use_container_width=True)
    st.download_button("Download gaps CSV", iss.to_csv(index=False), "gaps.csv")

if truth:
    with st.expander("Check against planted ground truth"):
        st.json(truth)
        found = set(iss["category"]) if not iss.empty else set()
        st.write("All 4 planted gap types found:", {"timing", "rounding_drift", "duplicate", "orphan_refund"} <= found)
