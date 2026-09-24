"""Local deterministic graph/data access used by the Tier A runner."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

@dataclass
class Txn:
    id: str; card_id: str; customer_id: str; ts: datetime; amount: float
    channel: str = "unknown"; product: str = "unknown"; risk_score: float = 0.0
    device_id: str = ""; region: str = ""; email: str = ""

class LocalGraph:
    def __init__(self, transactions=None, closed_cases=None):
        self.transactions = list(transactions or [])
        self.closed_cases = list(closed_cases or [])
        self.by_id = {t.id: t for t in self.transactions}
        self.by_card = defaultdict(list)
        self.by_device = defaultdict(set)
        for t in self.transactions:
            self.by_card[t.card_id].append(t)
            if t.device_id: self.by_device[t.device_id].add(t.card_id)
        for rows in self.by_card.values(): rows.sort(key=lambda x: x.ts)

    def txn_context(self, txn_id):
        t = self.by_id.get(str(txn_id)); return t
    def card_window(self, card_id, center_ts, hours=72):
        lo, hi = center_ts-timedelta(hours=hours), center_ts+timedelta(hours=hours)
        return [t for t in self.by_card.get(card_id, []) if lo <= t.ts <= hi]
    def card_baseline(self, card_id, before_ts):
        rows=[t for t in self.by_card.get(card_id, []) if t.ts < before_ts]
        amounts=sorted(t.amount for t in rows)
        return {"count":len(rows), "median": amounts[len(amounts)//2] if amounts else 0.0,
                "regions": list({t.region for t in rows if t.region}), "devices":list({t.device_id for t in rows if t.device_id})}
    def testing_sequence(self, card_id, ts):
        rows=self.card_window(card_id, ts, 2)
        small=[t for t in rows if t.channel == "online" and t.amount < 5 and t.ts <= ts]
        return len(small) >= 3 and any(t.amount >= 20 and t.ts >= ts for t in rows)
    def device_neighbors(self, device_id):
        return sorted(self.by_device.get(device_id, set()))
    def case_history(self, card_id):
        return [c for c in self.closed_cases if c.get("card_id") == card_id]
    def similar_closed_cases(self, card_id, device_id="", region=""):
        return [c for c in self.closed_cases if c.get("card_id")==card_id or (device_id and device_id in c.get("device_profiles",[])) or (region and region==c.get("region"))]
