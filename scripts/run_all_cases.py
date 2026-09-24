#!/usr/bin/env python3
import argparse, csv, json
from pathlib import Path
from agent.runner import demo_inputs, run_case
from agent.graph import LocalGraph, Txn

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--demo',action='store_true'); ap.add_argument('--out',default='out'); ap.add_argument('--cases',default='cases'); args=ap.parse_args()
    out=Path(args.out); cases_dir=Path(args.cases); (out/'traces').mkdir(parents=True,exist_ok=True); (out/'graphs').mkdir(parents=True,exist_ok=True); cases_dir.mkdir(parents=True,exist_ok=True)
    if not args.demo: raise SystemExit('Official dataset discovery is not included in this minimum pass. Re-run with --demo or add a loader for your supplied case pack.')
    tx, rows=demo_inputs(); graph=LocalGraph(tx)
    index=[]
    for row in rows:
        case,trace,flagged,affected=run_case(row,graph,'demo'); (cases_dir/(row['case_id']+'.json')).write_text(json.dumps(case,indent=2)); (out/'traces'/(row['case_id']+'.trace.json')).write_text(json.dumps(trace,indent=2))
        nodes=[{"id":flagged.id,"type":"Transaction","label":f"${flagged.amount:.2f}","role":"flagged","attrs":{"ts":flagged.ts.strftime('%Y-%m-%d %H:%M:%S'),"amount":flagged.amount,"channel":flagged.channel,"product":flagged.product,"risk_score":flagged.risk_score,"card_id":flagged.card_id}}]
        (out/'graphs'/(row['case_id']+'.graph.json')).write_text(json.dumps({"contract_version":"1.0","case_id":row['case_id'],"nodes":nodes,"edges":[]},indent=2))
        index.append({"case_id":row['case_id'],"opened_at":row.get('opened_at',''),"trigger_type":row.get('trigger_type','risk_score'),"card_id":flagged.card_id,"customer_id":flagged.customer_id,"flagged_txn_id":flagged.id,"risk_score":flagged.risk_score,"status":case['case']['status'],"verdict":case['case']['verdict'],"fraud_probability":case['case']['fraud_probability'],"pattern":case['case']['pattern'],"exposure_usd":case['case']['exposure_usd'],"final_actions":[x['action'] for x in case['next_best_actions']['final']],"sar_file":case['sar']['file'],"awaiting_approval_count":0,"tool_calls":case['tool_calls'],"latency_s":case['latency_s']})
    (out/'index.json').write_text(json.dumps({"contract_version":"1.0","generated_at":"2026-09-24T00:00:00Z","cases":index},indent=2)); (out/'closed_cases_lite.json').write_text('{}'); (out/'metrics.json').write_text(json.dumps({"contract_version":"1.0","generated_at":"2026-09-24T00:00:00Z","cases":[{"case_id":x['case_id'],"tool_calls":x['tool_calls'],"tokens":0,"latency_s":x['latency_s'],"validators_passed":True,"validator_failures":[]} for x in index],"totals":{"tool_calls":sum(x['tool_calls'] for x in index),"tokens":0,"latency_s":sum(x['latency_s'] for x in index)},"backtest":{"n":0},"calibration_bins":[]},indent=2))

if __name__=='__main__': main()
