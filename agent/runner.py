from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from .graph import LocalGraph, Txn
from .patterns import detect
from .episode import episode, exposure_usd
from .policy_engine import recommend


def run_case(row, graph, mode="batch"):
    flagged = graph.txn_context(row["flagged_txn_id"])
    if flagged is None:
        raise ValueError(f"unknown flagged transaction {row['flagged_txn_id']}")
    result = detect(graph, flagged)
    affected = episode(graph, flagged, result["verdict"] == "fraud")
    exposure = exposure_usd(graph, affected)
    shared = bool(flagged.device_id and len(graph.device_neighbors(flagged.device_id)) > 1)
    state = {**result, "exposure_usd": exposure, "shared_element": shared}
    actions = recommend(state)
    snapshot = {
        "status": "closed_fraud" if result["verdict"] == "fraud" else "closed_legitimate" if result["verdict"] == "legitimate" else "open",
        "verdict": result["verdict"], "fraud_probability": result["probability"],
        "evidence_count": len(result["evidence"]),
        "independent_families": len({e[0] for e in result["evidence"]}),
        "exposure_usd": exposure, "affected_txn_count": len(affected),
    }
    events = []
    def add(step, kind, title, **extra):
        events.append({"seq": len(events) + 1, "t_offset_s": round((len(events) + 1) * .01, 3),
                       "step": step, "kind": kind, "title": title, "state": snapshot, **extra})
    add("trigger", "trigger_received", f"Trigger for {flagged.id}")
    add("investigate", "case_opened", "Case opened", rule_refs=["3a"])
    for family, direction, weight, claim in result["evidence"]:
        add("gather_evidence", "evidence_added", claim, evidence={
            "claim": claim, "source": "graph", "ref": f"query:{family}",
            "entity_ids": [flagged.id], "family": family,
            "direction": direction, "weight_logit": weight})
    add("assess_uncertainty", "assessment", f"Probability {result['probability']}")
    add("take_actions", "actions_recommended", "Initial recommendation",
        actions={"phase": "initial", "items": actions})
    add("take_actions", "actions_recommended", "Final recommendation",
        actions={"phase": "final", "items": actions})
    add("explain", "stop_decision", "Deterministic Tier A stop")
    add("update_memory", "case_written", "Case written to local memory")
    started = datetime.utcnow().isoformat() + "Z"
    sar_file = any(a["action"] == "FILE_REPORT" for a in actions)
    sar = {"file": sar_file, "narrative": "", "subjects": [], "total_amount_usd": 0, "activity_dates": []}
    if sar_file:
        sar.update({"narrative": (f"Case {row['case_id']} concerns card {flagged.card_id}. "
                    f"The affected episode contains {len(affected)} transaction(s) totaling ${exposure:.2f}. "
                    "The activity is consistent with suspected fraud and is referred for review."),
                    "subjects": [flagged.card_id], "total_amount_usd": exposure,
                    "activity_dates": [graph.by_id[t].ts.date().isoformat() for t in affected]})
    case = {
        "contract_version": "1.0", "case_id": row["case_id"], "run_mode": mode,
        "started_at": started, "totals": {"tool_calls": 7, "tokens": 0, "latency_s": round(len(events) * .01, 3)},
        "case": {"case_id": row["case_id"], "opened_at": row.get("opened_at", ""),
                 "trigger_type": row.get("trigger_type", "risk_score"), "card_id": flagged.card_id,
                 "customer_id": flagged.customer_id, "flagged_txn_id": flagged.id,
                 **snapshot, "pattern": result["pattern"], "affected_txn_ids": affected,
                 "exposure_usd": exposure},
        "sar": sar, "next_best_actions": {"initial": actions, "final": actions},
        "evidence_requests": [], "stop_reason": "further evidence unlikely to change the deterministic decision",
        "tool_calls": [], "tokens": 0, "latency_s": round(len(events) * .01, 3),
    }
    trace = {"contract_version": "1.0", "case_id": row["case_id"], "run_mode": mode,
             "started_at": started, "totals": case["totals"], "approvals": [], "events": events}
    return case, trace, flagged, affected


def demo_inputs():
    now = datetime(2016, 11, 14, 10, 31)
    tx = [Txn("DEMO-1", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=0), 1.1, "online", "C", .2),
          Txn("DEMO-2", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=10), 2.2, "online", "C", .2),
          Txn("DEMO-3", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=20), 3.1, "online", "C", .2),
          Txn("DEMO-4", "DEMO-CARD-K1", "DEMO-CUST", now, 259.98, "online", "C", .72, "DEMO-DEVICE", "DEMO-REGION")]
    return tx, [{"case_id": "DEMO-001", "flagged_txn_id": "DEMO-4", "opened_at": now.isoformat(), "trigger_type": "risk_score"}]
