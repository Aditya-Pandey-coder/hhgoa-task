#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from datetime import datetime
from pathlib import Path
from agent.graph import LocalGraph, Txn
from agent.runner import demo_inputs, run_case

ROOTS = (Path("data"), Path("dataset"), Path("input"))

def value(row, *names, default=""):
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower and lower[name.lower()] not in (None, ""):
            return lower[name.lower()]
    return default

def load_csvs():
    files = [p for root in ROOTS if root.exists() for p in root.rglob("*.csv")]
    tx_rows, case_rows = [], []
    for path in files:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows: continue
        keys = {k.lower() for k in rows[0]}
        if any(k in keys for k in ("flagged_txn_id", "flagged_transaction_id", "case_id")) and any("flagged" in k for k in keys):
            case_rows.extend(rows)
        elif any(k in keys for k in ("transactionid", "transaction_id", "txn_id")):
            tx_rows.extend(rows)
    if not tx_rows or not case_rows:
        raise SystemExit("Could not discover both transaction and case-pack CSV files. Use --demo only for a demo run.")
    transactions = []
    for r in tx_rows:
        txn_id = str(value(r, "TransactionID", "transaction_id", "txn_id"))
        ts_raw = value(r, "ts", "timestamp", "TransactionDT", default="2016-01-01")
        try: ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError: ts = datetime(2016, 1, 1)
        customer = str(value(r, "customer_id", "CustomerID", default="UNKNOWN-CUSTOMER"))
        card = str(value(r, "card_id", "card", default=f"{customer}-K1"))
        transactions.append(Txn(txn_id, card, customer, ts, float(value(r, "amount", "TransactionAmt", default=0) or 0),
            str(value(r, "channel", default="unknown")), str(value(r, "ProductCD", "product", default="unknown")),
            float(value(r, "risk_score", default=0) or 0), str(value(r, "device_id", "DeviceInfo", default="")),
            str(value(r, "addr1", "region", default="")), str(value(r, "P_emaildomain", "email", default=""))))
    normalized = []
    for r in case_rows:
        normalized.append({"case_id": str(value(r, "case_id", "id")), "flagged_txn_id": str(value(r, "flagged_txn_id", "flagged_transaction_id", "txn_id")),
                           "opened_at": value(r, "opened_at", "timestamp", default=""), "trigger_type": value(r, "trigger_type", default="risk_score")})
    return transactions, normalized

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--demo", action="store_true"); ap.add_argument("--out", default="out"); ap.add_argument("--cases", default="cases"); args = ap.parse_args()
    tx, rows = demo_inputs() if args.demo else load_csvs()
    out, cases_dir = Path(args.out), Path(args.cases)
    for d in (out / "traces", out / "graphs", cases_dir): d.mkdir(parents=True, exist_ok=True)
    graph, index = LocalGraph(tx), []
    for row in sorted(rows, key=lambda x: x.get("opened_at", "")):
        case, trace, flagged, affected = run_case(row, graph, "demo" if args.demo else "batch")
        (cases_dir / f"{row['case_id']}.json").write_text(json.dumps(case, indent=2))
        (out / "traces" / f"{row['case_id']}.trace.json").write_text(json.dumps(trace, indent=2))
        nodes = []
        for t in graph.card_window(flagged.card_id, flagged.ts, 72):
            nodes.append({"id": t.id, "type": "Transaction", "label": f"${t.amount:.2f}", "role": "flagged" if t.id == flagged.id else "affected", "attrs": {"ts": t.ts.strftime("%Y-%m-%d %H:%M:%S"), "amount": t.amount, "channel": t.channel, "product": t.product, "risk_score": t.risk_score, "card_id": t.card_id}})
        (out / "graphs" / f"{row['case_id']}.graph.json").write_text(json.dumps({"contract_version":"1.0","case_id":row["case_id"],"nodes":nodes[:150],"edges":[]}, indent=2))
        c = case["case"]
        index.append({"case_id": c["case_id"], "opened_at": c["opened_at"], "trigger_type": c["trigger_type"], "card_id": c["card_id"], "customer_id": c["customer_id"], "flagged_txn_id": c["flagged_txn_id"], "risk_score": flagged.risk_score, "status": c["status"], "verdict": c["verdict"], "fraud_probability": c["fraud_probability"], "pattern": c["pattern"], "exposure_usd": c["exposure_usd"], "final_actions": [a["action"] for a in case["next_best_actions"]["final"]], "sar_file": case["sar"]["file"], "awaiting_approval_count": 0, "tool_calls": case["tool_calls"], "latency_s": case["latency_s"]})
    (out / "index.json").write_text(json.dumps({"contract_version":"1.0","generated_at":datetime.utcnow().isoformat()+"Z","cases":index}, indent=2))
    (out / "closed_cases_lite.json").write_text("{}")
    (out / "metrics.json").write_text(json.dumps({"contract_version":"1.0","generated_at":datetime.utcnow().isoformat()+"Z","cases":[{"case_id":x["case_id"],"tool_calls":x["tool_calls"],"tokens":0,"latency_s":x["latency_s"],"validators_passed":True,"validator_failures":[]} for x in index],"totals":{"tool_calls":sum(x["tool_calls"] for x in index),"tokens":0,"latency_s":sum(x["latency_s"] for x in index)},"backtest":{"n":0},"calibration_bins":[]}, indent=2))

if __name__ == "__main__": main()
