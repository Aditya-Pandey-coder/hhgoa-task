"""Contract validation helpers."""
import json
from pathlib import Path
from .policy_engine import ACTIONS, route

def validate_case(case, graph=None, trace=None):
    errors=[]; c=case.get("case",case)
    if case.get("contract_version") != "1.0": errors.append("contract_version")
    if c.get("verdict") not in {"fraud","legitimate","uncertain"}: errors.append("verdict")
    if c.get("pattern") not in {"card_testing","card_not_present_fraud","card_not_present_new_device","out_of_region_use","account_takeover","undocumented","none"}: errors.append("pattern")
    actions=case.get("next_best_actions",{}); finals=actions.get("final",[])
    for a in finals:
        if a.get("action") not in ACTIONS: errors.append("action")
        elif a.get("route") != route(a["action"],c.get("exposure_usd",0)): errors.append("route:"+a["action"])
        if "R" not in a.get("reason","") and "3a" not in a.get("reason",""): errors.append("reason")
    sar=case.get("sar",{})
    report=any(a.get("action")=="FILE_REPORT" for a in finals)
    if bool(sar.get("file")) != report: errors.append("sar.file parity")
    if c.get("verdict")=="legitimate" and (c.get("affected_txn_ids") or c.get("exposure_usd",0)!=0): errors.append("legitimate exposure")
    if trace:
        rec=[e for e in trace.get("events",[]) if e.get("kind")=="actions_recommended"]
        if rec and rec[0].get("actions",{}).get("items") != actions.get("initial"): errors.append("initial trace parity")
        if rec and rec[-1].get("actions",{}).get("items") != finals: errors.append("final trace parity")
    return errors

def validate_paths(cases_dir, out_dir):
    errors=[]
    for path in sorted(Path(cases_dir).glob("*.json")):
        case=json.loads(path.read_text()); trace_path=Path(out_dir)/"traces"/(path.stem+".trace.json")
        trace=json.loads(trace_path.read_text()) if trace_path.exists() else None
        errors += [f"{path.name}: {e}" for e in validate_case(case, trace=trace)]
    return errors
