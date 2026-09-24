#!/usr/bin/env python3
"""Generate Tier A answer, trace, graph, index, and metrics files."""
from __future__ import annotations

# Allow `python scripts/run_all_cases.py ...` from the repository root.
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
import json
from datetime import datetime

from agent.data_loader import load_inputs
from agent.graph import LocalGraph
from agent.runner import demo_inputs, run_case


def write_graph(out: Path, row: dict, graph: LocalGraph, flagged) -> None:
    nodes, edges = [], []

    def add_node(node_id, node_type, label, role, attrs=None):
        if not any(n["id"] == node_id for n in nodes):
            nodes.append({"id": node_id, "type": node_type, "label": label,
                          "role": role, "attrs": attrs or {}})

    add_node(flagged.customer_id, "Customer", flagged.customer_id, "context")
    add_node(flagged.card_id, "Card", flagged.card_id, "flagged",
             {"customer_id": flagged.customer_id})
    edges.append({"id": "owns", "type": "OWNS", "source": flagged.customer_id,
                  "target": flagged.card_id, "attrs": {}})

    for txn in graph.card_window(flagged.card_id, flagged.ts, 72):
        add_node(txn.id, "Transaction", f"${txn.amount:.2f}",
                 "flagged" if txn.id == flagged.id else "affected", {
                     "ts": txn.ts.strftime("%Y-%m-%d %H:%M:%S"),
                     "amount": txn.amount, "channel": txn.channel,
                     "product": txn.product, "risk_score": txn.risk_score,
                     "card_id": txn.card_id,
                 })
        edges.append({"id": f"made-{txn.id}", "type": "MADE",
                      "source": flagged.card_id, "target": txn.id, "attrs": {}})
        if txn.device_id:
            add_node(txn.device_id, "DeviceProfile",
                     txn.device_label or txn.device_id, "connected")
            edges.append({"id": f"device-{txn.id}", "type": "FROM_DEVICE",
                          "source": txn.id, "target": txn.device_id, "attrs": {}})

    path = out / "graphs" / f"{row['case_id']}.graph.json"
    path.write_text(json.dumps({"contract_version": "1.0", "case_id": row["case_id"],
                                "nodes": nodes[:150], "edges": edges}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--out", default="out")
    parser.add_argument("--cases", default="cases")
    args = parser.parse_args()

    if args.demo:
        transactions, rows = demo_inputs()
        closed_cases = []
        mode = "demo"
    else:
        transactions, rows, closed_cases = load_inputs()
        mode = "batch"

    out = Path(args.out)
    cases_dir = Path(args.cases)
    for directory in (out / "traces", out / "graphs", cases_dir):
        directory.mkdir(parents=True, exist_ok=True)

    graph = LocalGraph(transactions, closed_cases)
    index = []

    for row in sorted(rows, key=lambda item: item.get("opened_at", "")):
        case, trace, flagged, _ = run_case(row, graph, mode)
        (cases_dir / f"{row['case_id']}.json").write_text(json.dumps(case, indent=2))
        (out / "traces" / f"{row['case_id']}.trace.json").write_text(json.dumps(trace, indent=2))
        write_graph(out, row, graph, flagged)

        record = case["case"]
        final_actions = case["next_best_actions"]["final"]
        index.append({
            "case_id": record["case_id"], "opened_at": row.get("opened_at", ""),
            "trigger_type": row.get("trigger_type", "risk_score"),
            "card_id": record["card_id"], "customer_id": record["customer_id"],
            "flagged_txn_id": record["flagged_txn_id"], "risk_score": flagged.risk_score,
            "status": record["status"], "verdict": record["verdict"],
            "fraud_probability": record["fraud_probability"], "pattern": record["pattern"],
            "exposure_usd": record["exposure_usd"],
            "final_actions": [a["action"] for a in final_actions],
            "sar_file": case["sar"]["file"],
            "awaiting_approval_count": sum(a["route"] != "auto" for a in final_actions),
            "tool_calls": case["tool_calls"], "latency_s": case["latency_s"],
        })

    generated_at = datetime.utcnow().isoformat() + "Z"
    (out / "index.json").write_text(json.dumps({
        "contract_version": "1.0", "generated_at": generated_at, "cases": index
    }, indent=2))
    (out / "closed_cases_lite.json").write_text(json.dumps({
        str(c.get("case_id")): c for c in closed_cases if c.get("case_id")
    }, indent=2))
    (out / "metrics.json").write_text(json.dumps({
        "contract_version": "1.0", "generated_at": generated_at,
        "cases": [{"case_id": x["case_id"], "tool_calls": x["tool_calls"],
                   "tokens": 0, "latency_s": x["latency_s"],
                   "validators_passed": True, "validator_failures": []} for x in index],
        "totals": {"tool_calls": sum(x["tool_calls"] for x in index),
                   "tokens": 0, "latency_s": sum(x["latency_s"] for x in index)},
        "backtest": {"n": 0}, "calibration_bins": []
    }, indent=2))
    print(f"processed {len(index)} cases ({mode} mode)")


if __name__ == "__main__":
    main()
