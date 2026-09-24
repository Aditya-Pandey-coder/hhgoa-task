"""Strict answer and trace validation."""
from pathlib import Path
import json
from .policy_engine import ACTIONS,route
PATTERNS={'card_testing','card_not_present_fraud','card_not_present_new_device','out_of_region_use','account_takeover','undocumented','none'}
def validate_case(case,trace=None,graph=None):
    e=[]; c=case.get('case',{}); required=('case_id','case','evidence_requests','next_best_actions','sar','stop_reason','tool_calls','tokens','latency_s')
    e += [f'missing:{x}' for x in required if x not in case]
    if c.get('status') not in {'open','closed_fraud','closed_legitimate','escalated'}: e.append('status')
    if c.get('verdict') not in {'fraud','legitimate','uncertain'}: e.append('verdict')
    if c.get('pattern') not in PATTERNS: e.append('pattern')
    if c.get('pattern')=='undocumented' and not c.get('pattern_description'): e.append('pattern_description')
    if not isinstance(c.get('fraud_probability'),(int,float)) or not 0<=c['fraud_probability']<=1: e.append('probability')
    if not isinstance(c.get('affected_txn_ids'),list) or not isinstance(c.get('evidence'),list): e.append('list fields')
    if c.get('verdict')=='legitimate' and (c.get('affected_txn_ids') or c.get('exposure_usd')!=0): e.append('legitimate exposure')
    if graph:
        total=round(sum(abs(graph.by_id[x].amount) for x in c.get('affected_txn_ids',[]) if x in graph.by_id),2)
        if total!=round(float(c.get('exposure_usd',0)),2): e.append('exposure mismatch')
        for x in c.get('affected_txn_ids',[]):
            if x not in graph.by_id: e.append(f'unknown txn:{x}')
    actions=case.get('next_best_actions',{}); initial=actions.get('initial'); final=actions.get('final')
    if not isinstance(initial,list) or not isinstance(final,list): e.append('actions')
    for a in (initial or [])+(final or []):
        if a.get('action') not in ACTIONS: e.append('action')
        elif a.get('route')!=route(a['action'],c.get('exposure_usd',0)): e.append('route')
        if not any(r in a.get('reason','') for r in ('R1','R2','R3','R4','R5','R6','R7','R8','R9','R10','3a')): e.append('reason')
    if not case.get('evidence_requests') and initial!=final: e.append('initial-final')
    sar=case.get('sar',{}); report=any(a.get('action')=='FILE_REPORT' for a in (final or []))
    if bool(sar.get('file'))!=report: e.append('sar parity')
    if not sar.get('file') and any(sar.get(k) not in ('',[],0) for k in ('narrative','subjects','total_amount_usd','activity_dates')): e.append('empty sar')
    if sar.get('file'):
        if not 6<=len([s for s in sar.get('narrative','').split('.') if s.strip()])<=12: e.append('sar sentence count')
        if sar.get('total_amount_usd')!=c.get('exposure_usd'): e.append('sar amount')
        if len(sar.get('activity_dates',[]))!=2: e.append('sar dates')
    if trace:
        rec=[x for x in trace.get('events',[]) if x.get('kind')=='actions_recommended']
        if not rec: e.append('trace actions missing')
        elif rec[0].get('actions',{}).get('items')!=initial: e.append('trace initial parity')
        elif rec[-1].get('actions',{}).get('items')!=final: e.append('trace final parity')
    return e
def validate_paths(cases_dir,out_dir,graph=None):
    errors=[]
    for p in sorted(Path(cases_dir).glob('*.json')):
        case=json.loads(p.read_text()); tp=Path(out_dir)/'traces'/(p.stem+'.trace.json'); trace=json.loads(tp.read_text()) if tp.exists() else None
        errors += [f'{p.name}: {x}' for x in validate_case(case,trace,graph)]
    return errors
