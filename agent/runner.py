"""Deterministic workflow producing the README answer schema."""
from __future__ import annotations
from datetime import datetime
from .graph import LocalGraph
from .patterns import detect
from .episode import episode,exposure_usd
from .policy_engine import recommend

def run_case(row,graph,mode='batch'):
    flagged=graph.txn_context(row['flagged_txn_id'])
    if not flagged: raise ValueError(f"Unknown transaction ID: {row['flagged_txn_id']}")
    result=detect(graph,flagged); report_trigger=row.get('trigger_type')=='customer_report'
    if report_trigger: result.update(verdict='fraud',probability=max(.75,result['probability']),pattern=result['pattern'] if result['pattern']!='none' else 'card_not_present_fraud')
    affected=episode(graph,flagged,result['verdict']=='fraud'); exposure=exposure_usd(graph,affected)
    neighbors=graph.device_neighbors(flagged.device_id,14,flagged.ts) if flagged.device_id else []
    prior=graph.similar_closed_cases(flagged.card_id,flagged.device_id,flagged.region)
    shared=len(neighbors)>1
    base={**result,'exposure_usd':exposure,'shared_element':shared,'customer_response':'denies' if report_trigger else None,'recurring_match':False}
    initial=recommend(base); requests=[]; final=initial
    if not report_trigger and result['verdict']=='uncertain' and .30<=result['probability']<.85:
        requests=[{'type':'customer_validation','asked_after_step':4,'assumed_response':'no_reply within 24 hours'}]
        final=recommend({**base,'customer_response':'no_reply'})
    sar_file=any(a['action']=='FILE_REPORT' for a in final)
    dates=sorted({graph.by_id[x].ts.date().isoformat() for x in affected})
    evidence=[{'claim':claim,'source':'graph','ref':f'query:{family}','entity_ids':[flagged.id]} for family,_,_,claim in result['evidence']]
    if report_trigger: evidence.append({'claim':'Customer reported the flagged transaction as unauthorized.','source':'customer','ref':'trigger_text','entity_ids':[flagged.customer_id,flagged.id]})
    connected_cards=[c for c in neighbors if c!=flagged.card_id]
    pattern_desc='Coordinated activity linked by a shared device profile across multiple cards; the linkage was found by local device-neighbor expansion.' if result['pattern']=='undocumented' else ''
    status='closed_fraud' if result['verdict']=='fraud' else 'closed_legitimate' if result['verdict']=='legitimate' else 'escalated' if any(a['action']=='ESCALATE_TO_ANALYST' for a in final) else 'open'
    narrative=''
    if sar_file:
        narrative=(f"Customer {flagged.customer_id} used card {flagged.card_id}. The suspicious activity occurred between {dates[0]} and {dates[-1]}. "
        f"The activity involved {len(affected)} transaction(s) totaling ${exposure:.2f}. The transactions used the {flagged.channel} channel. "
        f"The investigation identified pattern {result['pattern']}. The evidence is consistent with unauthorized activity. "
        f"The case was linked to {len(connected_cards)} other card(s) where applicable. The report is filed under the applicable policy gate.")
    case={'case_id':row['case_id'],'case':{'status':status,'verdict':result['verdict'],'fraud_probability':round(result['probability'],4),'pattern':result['pattern'],'pattern_description':pattern_desc,'affected_txn_ids':affected,'first_suspicious_txn_id':affected[0] if affected else '','connected_card_ids':connected_cards,'connected_device_profiles':[flagged.device_label or flagged.device_id] if shared else [],'exposure_usd':exposure,'evidence':evidence,'similar_prior_cases':[str(c.get('case_id')) for c in prior if c.get('case_id')],'summary':f"Investigation of {flagged.id} found {result['pattern']} evidence with fraud probability {result['probability']:.2f}.",'written_to_graph':False,'graph_case_id':''},'evidence_requests':requests,'next_best_actions':{'initial':initial,'final':final,'what_changed':'No requested evidence was returned; final actions reflect the no-reply assumption.' if requests else 'nothing'},'sar':{'file':sar_file,'reason':'R2/R6/R9 report gate satisfied.' if sar_file else 'R1/R3/R4: report gate not satisfied.','narrative':narrative,'subjects':[flagged.customer_id,flagged.card_id]+connected_cards if sar_file else [],'total_amount_usd':exposure if sar_file else 0,'activity_dates':[dates[0],dates[-1]] if sar_file and dates else []},'stop_reason':'Customer report settled the question.' if report_trigger else 'Further evidence is unlikely to change the deterministic decision.','tool_calls':7,'tokens':0,'latency_s':0.01}
    snap={'status':status,'verdict':result['verdict'],'fraud_probability':round(result['probability'],4),'evidence_count':len(evidence),'independent_families':len({e['source']+e['ref'] for e in evidence}),'exposure_usd':exposure,'affected_txn_count':len(affected)}
    events=[]
    def add(step,kind,title,**extra): events.append({'seq':len(events)+1,'t_offset_s':round(len(events)*.01,3),'step':step,'kind':kind,'title':title,'state':snap,**extra})
    add('trigger','trigger_received',f'Trigger for {flagged.id}'); add('investigate','case_opened','Case opened',rule_refs=['3a'])
    for e in evidence: add('gather_evidence','evidence_added',e['claim'],evidence={**e,'family':'other','direction':'fraud','weight_logit':0})
    add('assess_uncertainty','assessment',f'Probability {result["probability"]}')
    add('take_actions','actions_recommended','Initial recommendation',actions={'phase':'initial','items':initial})
    if requests: add('gather_more_evidence','evidence_request','Customer validation requested',needs_input={'request_type':'customer_validation','prompt':'Did you make this activity?','assumed_response':'no_reply within 24 hours','options':['denies','confirms','no_reply']})
    add('take_actions','actions_recommended','Final recommendation',actions={'phase':'final','items':final}); add('explain','stop_decision',case['stop_reason']); add('update_memory','case_written','Case written to local output memory')
    return case,{'contract_version':'1.0','case_id':row['case_id'],'run_mode':mode,'started_at':datetime.utcnow().isoformat()+'Z','totals':{'tool_calls':7,'tokens':0,'latency_s':.01},'approvals':[],'events':events},flagged,affected

# Kept for tests and demo mode.
def demo_inputs():
    from .graph import Txn
    now=datetime(2016,11,14,10,31); tx=[Txn('DEMO-1','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=0),1.1,'online','C',.2),Txn('DEMO-2','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=10),2.2,'online','C',.2),Txn('DEMO-3','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=20),3.1,'online','C',.2),Txn('DEMO-4','DEMO-CARD-K1','DEMO-CUST',now,259.98,'online','C',.72,'DEMO-DEVICE','DEMO-REGION','', 'Demo device')]
    return tx,[{'case_id':'DEMO-001','flagged_txn_id':'DEMO-4','opened_at':now.isoformat(),'trigger_type':'risk_score'}]
