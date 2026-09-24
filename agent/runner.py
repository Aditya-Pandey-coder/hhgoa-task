"""Deterministic workflow producing the Tier A answer and trace schemas."""
from __future__ import annotations

from datetime import datetime, timezone

from .episode import episode, exposure_usd
from .graph import LocalGraph, Txn
from .patterns import detect
from .policy_engine import recommend


UNDOCUMENTED_PATTERN_DESCRIPTION = (
    "Coordinated activity linked by a shared device profile across multiple cards; "
    "the linkage was found by local device-neighbor expansion."
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_case(row: dict, graph: LocalGraph, mode: str = "batch"):
    flagged = graph.txn_context(row["flagged_txn_id"])
    if flagged is None:
        raise ValueError(f"unknown flagged transaction {row['flagged_txn_id']}")

    result = detect(graph, flagged)
    affected = episode(graph, flagged, result["verdict"] == "fraud")
    exposure = exposure_usd(graph, affected)
    connected_cards = graph.device_neighbors(flagged.device_id) if flagged.device_id else []
    shared = len(connected_cards) > 1
    state = {
        **result,
        "exposure_usd": exposure,
        "shared_element": shared,
        "customer_response": "denies" if row.get("trigger_type") == "customer_report" else None,
    }
    final_actions = recommend(state)
    initial_actions = list(final_actions)

    evidence = []
    for family, direction, weight, claim in result["evidence"]:
        evidence.append({
            "claim": claim,
            "source": "graph",
            "ref": f"query:{family}",
            "entity_ids": [flagged.id],
        })

    if row.get("trigger_type") == "customer_report":
        evidence.append({
            "claim": "Customer reported the flagged transaction as unauthorized.",
            "source": "customer",
            "ref": "trigger_text",
            "entity_ids": [flagged.customer_id, flagged.id],
        })

    status = (
        "closed_fraud" if result["verdict"] == "fraud"
        else "closed_legitimate" if result["verdict"] == "legitimate"
        else "escalated" if any(a["action"] == "ESCALATE_TO_ANALYST" for a in final_actions)
        else "open"
    )
    timestamps = sorted(graph.by_id[txn_id].ts.date().isoformat() for txn_id in affected)
    sar_file = any(a["action"] == "FILE_REPORT" for a in final_actions)
    pattern_description = (
        UNDOCUMENTED_PATTERN_DESCRIPTION
        if result["pattern"] == "undocumented"
        else ""
    )

    sar = {
        "file": sar_file,
        "reason": "R2/R6/R9: report gate satisfied." if sar_file else "R1/R3: report gate not satisfied.",
        "narrative": "",
        "subjects": [],
        "total_amount_usd": 0,
        "activity_dates": [],
    }
    if sar_file:
        sar.update({
            "narrative": (
                f"Customer {flagged.customer_id} used card {flagged.card_id}. "
                f"Suspicious activity occurred between {timestamps[0]} and {timestamps[-1]}. "
                f"The activity involved {len(affected)} transaction(s) totaling ${exposure:.2f}. "
                f"The transactions used the {flagged.channel} channel. "
                f"The investigation identified the {result['pattern']} pattern. "
                "The evidence is consistent with unauthorized activity. "
                "The case was reviewed under the applicable fraud policy. "
                "The report is filed because the policy report gate was met."
            ),
            "subjects": [flagged.customer_id, flagged.card_id, *[c for c in connected_cards if c != flagged.card_id]],
            "total_amount_usd": exposure,
            "activity_dates": [timestamps[0], timestamps[-1]],
        })

    case = {
        "contract_version": "1.0",
        "case_id": row["case_id"],
        "run_mode": mode,
        "started_at": utc_now_iso(),
        "totals": {"tool_calls": 7, "tokens": 0, "latency_s": 0.01},
        "case": {
            "case_id": row["case_id"],
            "status": status,
            "verdict": result["verdict"],
            "fraud_probability": round(result["probability"], 4),
            "pattern": result["pattern"],
            "pattern_description": pattern_description,
            "affected_txn_ids": affected,
            "first_suspicious_txn_id": affected[0] if affected else "",
            "connected_card_ids": [c for c in connected_cards if c != flagged.card_id],
            "connected_device_profiles": [flagged.device_id] if flagged.device_id and shared else [],
            "exposure_usd": exposure,
            "evidence": evidence,
            "similar_prior_cases": [],
            "summary": (
                f"Investigation of {flagged.id} found {result['pattern']} evidence "
                f"with fraud probability {result['probability']:.2f}."
            ),
            "written_to_graph": False,
            "graph_case_id": "",
            "card_id": flagged.card_id,
            "customer_id": flagged.customer_id,
            "flagged_txn_id": flagged.id,
            "opened_at": row.get("opened_at", ""),
            "trigger_type": row.get("trigger_type", "risk_score"),
        },
        "evidence_requests": [],
        "next_best_actions": {
            "initial": initial_actions,
            "final": final_actions,
            "what_changed": "nothing",
        },
        "sar": sar,
        "stop_reason": "Further evidence is unlikely to change the deterministic decision.",
        "tool_calls": 7,
        "tokens": 0,
        "latency_s": 0.01,
    }

    snapshot = {
        "status": status,
        "verdict": result["verdict"],
        "fraud_probability": round(result["probability"], 4),
        "evidence_count": len(evidence),
        "independent_families": len({item["source"] for item in evidence}),
        "exposure_usd": exposure,
        "affected_txn_count": len(affected),
    }
    events = []

    def add_event(step, kind, title, **extra):
        events.append({
            "seq": len(events) + 1,
            "t_offset_s": round(len(events) * 0.01, 3),
            "step": step,
            "kind": kind,
            "title": title,
            "state": snapshot,
            **extra,
        })

    add_event("trigger", "trigger_received", f"Trigger for {flagged.id}")
    add_event("investigate", "case_opened", "Case opened", rule_refs=["3a"])
    for item in evidence:
        add_event(
            "gather_evidence",
            "evidence_added",
            item["claim"],
            evidence={**item, "family": "other", "direction": "fraud", "weight_logit": 0},
        )
    add_event("assess_uncertainty", "assessment", f"Probability {result['probability']}")
    add_event(
        "take_actions",
        "actions_recommended",
        "Initial recommendation",
        actions={"phase": "initial", "items": initial_actions},
    )
    add_event(
        "take_actions",
        "actions_recommended",
        "Final recommendation",
        actions={"phase": "final", "items": final_actions},
    )
    add_event("explain", "stop_decision", case["stop_reason"])
    add_event("update_memory", "case_written", "Case written to local output memory")

    trace = {
        "contract_version": "1.0",
        "case_id": row["case_id"],
        "run_mode": mode,
        "started_at": case["started_at"],
        "totals": case["totals"],
        "approvals": [],
        "events": events,
    }
    return case, trace, flagged, affected


def demo_inputs():
    now = datetime(2016, 11, 14, 10, 31)
    tx = [
        Txn("DEMO-1", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=0), 1.1, "online", "C", 0.2),
        Txn("DEMO-2", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=10), 2.2, "online", "C", 0.2),
        Txn("DEMO-3", "DEMO-CARD-K1", "DEMO-CUST", now.replace(minute=20), 3.1, "online", "C", 0.2),
        Txn("DEMO-4", "DEMO-CARD-K1", "DEMO-CUST", now, 259.98, "online", "C", 0.72, "DEMO-DEVICE", "DEMO-REGION", "", "Demo device"),
    ]
    return tx, [{
        "case_id": "DEMO-001",
        "flagged_txn_id": "DEMO-4",
        "opened_at": now.isoformat(),
        "trigger_type": "risk_score",
    }]
