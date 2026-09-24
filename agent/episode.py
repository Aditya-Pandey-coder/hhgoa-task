"""Episode membership and exposure calculation."""
from __future__ import annotations
from .graph import LocalGraph, Txn


def episode(graph: LocalGraph, flagged: Txn, fraud: bool = True, hours: int = 72) -> list[str]:
    """Return deterministic affected transaction IDs for a fraud episode.

    Legitimate and unresolved cases have no affected episode. Fraud cases include
    the flagged transaction and nearby same-card activity; testing probes are kept
    when they occur in the same window.
    """
    if not fraud:
        return []
    rows = graph.card_window(flagged.card_id, flagged.ts, hours)
    selected = []
    for txn in rows:
        if txn.id == flagged.id:
            selected.append(txn.id)
            continue
        if txn.channel == "online" and abs((txn.ts - flagged.ts).total_seconds()) <= hours * 3600:
            selected.append(txn.id)
    return sorted(set(selected), key=lambda txn_id: graph.by_id[txn_id].ts)


def exposure_usd(graph: LocalGraph, txn_ids: list[str]) -> float:
    return round(sum(abs(graph.by_id[txn_id].amount) for txn_id in txn_ids), 2)
