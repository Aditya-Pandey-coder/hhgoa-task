"""Local normalized graph used by the deterministic backend."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timedelta

@dataclass
class Txn:
    id: str
    card_id: str
    customer_id: str
    ts: datetime
    amount: float
    channel: str = "unknown"
    product: str = "unknown"
    risk_score: float = 0.0
    device_id: str = ""
    region: str = ""
    email: str = ""
    device_label: str = ""

class LocalGraph:
    def __init__(self, transactions=None, closed_cases=None):
        self.transactions=list(transactions or [])
        self.closed_cases=list(closed_cases or [])
        self.by_id={str(t.id): t for t in self.transactions}
        self.by_card=defaultdict(list); self.by_device=defaultdict(set); self.by_region=defaultdict(set)
        for t in self.transactions:
            self.by_card[t.card_id].append(t)
            if t.device_id: self.by_device[t.device_id].add(t.card_id)
            if t.region: self.by_region[t.region].add(t.card_id)
        for rows in self.by_card.values(): rows.sort(key=lambda x:x.ts)
    def txn_context(self, txn_id): return self.by_id.get(str(txn_id))
    def card_window(self, card_id, center_ts, hours=72):
        lo=center_ts-timedelta(hours=hours); hi=center_ts+timedelta(hours=hours)
        return [t for t in self.by_card.get(card_id,[]) if lo<=t.ts<=hi]
    def card_baseline(self, card_id, before_ts):
        rows=[t for t in self.by_card.get(card_id,[]) if t.ts<before_ts]; amounts=sorted(t.amount for t in rows)
        return {"count":len(rows),"median":amounts[len(amounts)//2] if amounts else 0.0,
                "regions":sorted({t.region for t in rows if t.region}),"devices":sorted({t.device_id for t in rows if t.device_id}),
                "products":sorted({t.product for t in rows if t.product})}
    def testing_sequence(self, card_id, ts):
        rows=sorted(self.card_window(card_id,ts,1),key=lambda x:x.ts)
        small=[t for t in rows if t.ts<=ts and t.channel=="online" and abs(t.amount)<5]
        return len(small)>=3 and any(t.ts>=ts and t.amount>=20 for t in rows)
    def device_neighbors(self, device_id, window_days=None, center_ts=None):
        if not window_days or not center_ts: return sorted(self.by_device.get(device_id,set()))
        lo=center_ts-timedelta(days=window_days); hi=center_ts+timedelta(days=window_days)
        return sorted({t.card_id for t in self.transactions if t.device_id==device_id and lo<=t.ts<=hi})
    def region_neighbors(self, region): return sorted(self.by_region.get(region,set()))
    def case_history(self, card_id): return [c for c in self.closed_cases if str(c.get("card_id",''))==str(card_id)]
    def similar_closed_cases(self, card_id, device_id="", region=""):
        out=[]
        for c in self.closed_cases:
            devices=c.get("device_profiles",[]) if isinstance(c.get("device_profiles",[]),list) else str(c.get("device_profiles","")).split("|")
            if str(c.get("card_id",''))==str(card_id) or (device_id and device_id in devices) or (region and str(c.get("region",''))==str(region)): out.append(c)
        return out
