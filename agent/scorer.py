"""Episode calculation and interpretable deterministic scoring."""
from __future__ import annotations
from .graph import LocalGraph

def episode(graph: LocalGraph, flagged, fraud=True):
    if not fraud: return []
    rows=graph.card_window(flagged.card_id, flagged.ts, 72)
    if len(rows) <= 1: return [flagged.id]
    return [t.id for t in rows if t.id == flagged.id or (t.channel == "online" and (t.amount >= 5 or graph.testing_sequence(flagged.card_id, flagged.ts)))]

def score_case(graph, flagged):
    evidence=[]; p=0.50; pattern="none"
    testing=graph.testing_sequence(flagged.card_id, flagged.ts)
    if testing:
        p += .28; pattern="card_testing"; evidence.append(("sequence","fraud",.28,"Testing sequence detected"))
    baseline=graph.card_baseline(flagged.card_id, flagged.ts)
    new_device=bool(flagged.device_id and flagged.device_id not in baseline["devices"])
    if flagged.channel == "online" and new_device:
        p += .12; pattern = "card_not_present_new_device" if pattern == "none" else pattern
        evidence.append(("device","fraud",.12,"New device for card"))
    if flagged.region and baseline["regions"] and flagged.region not in baseline["regions"]:
        p += .10
        if pattern == "none": pattern="out_of_region_use"
        evidence.append(("region","fraud",.10,"Region is new for card"))
    if flagged.risk_score >= .70: p += .08; evidence.append(("identity_flags","fraud",.08,"High source risk score"))
    if baseline["count"] and flagged.amount <= max(2, baseline["median"]*1.02):
        p -= .10; evidence.append(("recurring","legit",-.10,"Amount is near card baseline"))
    if not evidence: evidence.append(("baseline_deviation","neutral",0.0,"No strong deterministic signal"))
    p=max(.01,min(.99,p))
    verdict="fraud" if p >= .70 else ("legitimate" if p < .30 else "uncertain")
    if verdict == "legitimate": pattern="none"
    return {"probability":round(p,4),"verdict":verdict,"pattern":pattern,"evidence":evidence,"testing":testing,"new_device":new_device}
