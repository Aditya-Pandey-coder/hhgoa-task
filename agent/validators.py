"""Strict checks for the README Answer Format and interface contract."""
from pathlib import Path
import json
from .policy_engine import ACTIONS, route
PATTERNS={'card_testing','card_not_present_fraud','card_not_present_new_device','out_of_region_use','account_takeover','undocumented','none'}
def validate_case(case,trace=None,graph=None):
    errors=[]; c=case.get('case',{})
    required=('case_id','case','evidence_requests','next_best_actions','sar','stop_reason','tool_calls','tokens','latency_s')
    errors += [f'missing:{k}' for k in required if k not in case]
    if not isinstance(case.get('case_id'),str): errors.append('case_id:type')
    if c.get('status') not in {'open','closed_fraud','closed_legitimate','escalated'}: errors.append('status')
    if c.get('verdict') not in {'fraud','legitimate','uncertain'}: errors.append('verdict')
    if c.get('pattern') not in PATTERNS: errors.append('pattern')
    if c.get('pattern')=='undocumented' and not c.get('pattern_description'): errors.append('pattern_description')
    if not isinstance(c.get('fraud_probability'),(int,float)) or not 0<=c.get('fraud_probability',-1)<=1: errors.append('probability')
    if c.get('verdict')=='legitimate' and (c.get('affected_txn_ids') or c.get('exposure_usd')!=0): errors.append('legitimate exposure')
    if round(float(c.get('exposure_usd',0)),2)<0: errors.append('exposure')
    actions=case.get('next_best_actions',{}); initial=actions.get('initial',[]); final=actions.get('final',[])
    for a in initial+final:
        if a.get('action') not in ACTIONS: errors.append('action')
        elif a.get('route')!=route(a['action'],c.get('exposure_usd',0)): errors.append('route:'+a['action'])
        if not any(r in a.get('reason','') for r in ('R1','R2','R3','R4','R5','R6','R7','R8','R9','R10','3a')): errors.append('reason')
    if not case.get('evidence_requests') and initial!=final: errors.append('initial-final')
    sar=case.get('sar',{}); report=any(a.get('action')=='FILE_REPORT' for a in final)
    if bool(sar.get('file'))!=report: errors.append('sar parity')
    if not sar.get('file') and any(sar.get(k) not in ('',[],0) for k in ('narrative','subjects','total_amount_usd','activity_dates')): errors.append('empty sar')
    if trace:
        rec=[e for e in trace.get('events',[]) if e.get('kind')=='actions_recommended']
        if not rec: errors.append('trace actions missing')
        else:
            if rec[0].get('actions',{}).get('items')!=initial: errors.append('trace initial parity')
            if rec[-1].get('actions',{}).get('items')!=final: errors.append('trace final parity')
    return errors
def validate_paths(cases_dir,out_dir):
    errors=[]
    for p in sorted(Path(cases_dir).glob('*.json')):
        case=json.loads(p.read_text()); tp=Path(out_dir)/'traces'/(p.stem+'.trace.json'); trace=json.loads(tp.read_text()) if tp.exists() else None
        errors += [f'{p.name}: {e}' for e in validate_case(case,trace=trace)]
    return errors
