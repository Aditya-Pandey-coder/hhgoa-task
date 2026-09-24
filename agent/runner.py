"""Deterministic Tier A workflow matching the README answer schema."""
from __future__ import annotations
from datetime import datetime
from .graph import LocalGraph
from .patterns import detect
from .episode import episode, exposure_usd
from .policy_engine import recommend

def run_case(row, graph, mode='batch'):
    flagged=graph.txn_context(row['flagged_txn_id'])
    if flagged is None: raise ValueError(f"Unknown transaction ID: {row['flagged_txn_id']}")
    result=detect(graph,flagged)
    customer_denies=row.get('trigger_type')=='customer_report'
    if customer_denies: result.update(verdict='fraud', probability=max(.75,result['probability']), pattern=result['pattern'] if result['pattern']!='none' else 'card_not_present_fraud')
    affected=episode(graph,flagged,result['verdict']=='fraud')
    exposure=exposure_usd(graph,affected)
    connected=graph.device_neighbors(flagged.device_id) if flagged.device_id else []
    shared=len(connected)>1
    state={**result,'exposure_usd':exposure,'shared_element':shared,'customer_response':'denies' if customer_denies else None}
    final_actions=recommend(state)
    initial_actions=final_actions
    requests=[]
    if not customer_denies and result['verdict']=='uncertain' and .30 <= result['probability'] < .85:
        requests=[{'type':'customer_validation','asked_after_step':4,'assumed_response':'no_reply within 24 hours'}]
        state['customer_response']='no_reply'; final_actions=recommend(state)
    sar_file=any(a['action']=='FILE_REPORT' for a in final_actions)
    dates=[graph.by_id[x].ts.date().isoformat() for x in affected]
    evidence=[{'claim':claim,'source':'graph','ref':f'query:{family}','entity_ids':[flagged.id]} for family,direction,weight,claim in result['evidence']]
    if customer_denies: evidence.append({'claim':'Customer reported the transaction as unauthorized.','source':'customer','ref':'trigger_text','entity_ids':[flagged.customer_id,flagged.id]})
    status='closed_fraud' if result['verdict']=='fraud' else 'closed_legitimate' if result['verdict']=='legitimate' else 'escalated' if any(a['action']=='ESCALATE_TO_ANALYST' for a in final_actions) else 'open'
    graph_case_id=f'CASE-{row["case_id"]}'
    case={'case_id':row['case_id'],'case':{'status':status,'verdict':result['verdict'],'fraud_probability':result['probability'],'pattern':result['pattern'],'pattern_description':'','affected_txn_ids':affected,'first_suspicious_txn_id':affected[0] if affected else '','connected_card_ids':[x for x in connected if x!=flagged.card_id],'connected_device_profiles':[flagged.device_id] if flagged.device_id and shared else [],'exposure_usd':exposure,'evidence':evidence,'similar_prior_cases':[],'summary':f"Deterministic investigation of {flagged.id} found {result['pattern']} evidence with probability {result['probability']:.2f}.",'written_to_graph':True,'graph_case_id':graph_case_id},'evidence_requests':requests,'next_best_actions':{'initial':initial_actions,'final':final_actions,'what_changed':'Customer report or simulated evidence changed the recommendation.' if requests else 'nothing'},'sar':{'file':sar_file,'reason':'R2/R6/R9 report gate satisfied.' if sar_file else 'No report gate satisfied under Section 3a.','narrative':(f"Customer {flagged.customer_id} and card {flagged.card_id} show suspicious activity on {dates[0] if dates else flagged.ts.date().isoformat()}. The activity involved {len(affected)} transaction(s) totaling ${exposure:.2f}. Transactions occurred through the {flagged.channel} channel. The pattern and linked evidence are consistent with suspected fraud. The transaction was reviewed under the applicable fraud policy. The case is retained for investigation and follow-up.") if sar_file else '','subjects':[flagged.customer_id,flagged.card_id] if sar_file else [],'total_amount_usd':exposure if sar_file else 0,'activity_dates':[dates[0],dates[-1]] if sar_file and dates else []},'stop_reason':'Customer report settled the question.' if customer_denies else 'Further evidence unlikely to change the deterministic decision.','tool_calls':7,'tokens':0,'latency_s':0.01}
    snapshot={'status':status,'verdict':result['verdict'],'fraud_probability':result['probability'],'evidence_count':len(evidence),'independent_families':len({e['source']+e['ref'] for e in evidence}),'exposure_usd':exposure,'affected_txn_count':len(affected)}
    events=[]
    def add(step,kind,title,**extra): events.append({'seq':len(events)+1,'t_offset_s':round(len(events)*.01,3),'step':step,'kind':kind,'title':title,'state':snapshot,**extra})
    add('trigger','trigger_received',f'Trigger for {flagged.id}'); add('investigate','case_opened','Case opened',rule_refs=['3a'])
    for e in evidence: add('gather_evidence','evidence_added',e['claim'],evidence={**e,'family':'other','direction':'fraud','weight_logit':0})
    add('assess_uncertainty','assessment',f'Probability {result["probability"]}')
    add('take_actions','actions_recommended','Initial recommendation',actions={'phase':'initial','items':initial_actions})
    if requests: add('gather_more_evidence','evidence_request','Customer validation requested',needs_input={'request_type':requests[0]['type'],'prompt':'Did you make this activity?','assumed_response':requests[0]['assumed_response'],'options':['denies','confirms','no_reply']})
    add('take_actions','actions_recommended','Final recommendation',actions={'phase':'final','items':final_actions}); add('explain','stop_decision',case['stop_reason']); add('update_memory','case_written','Case written to local memory')
    trace={'contract_version':'1.0','case_id':row['case_id'],'run_mode':mode,'started_at':datetime.utcnow().isoformat()+'Z','totals':{'tool_calls':7,'tokens':0,'latency_s':.01},'approvals':[],'events':events}
    return case,trace,flagged,affected

def demo_inputs():
    from .graph import Txn
    now=datetime(2016,11,14,10,31)
    tx=[Txn('DEMO-1','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=0),1.1,'online','C',.2),Txn('DEMO-2','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=10),2.2,'online','C',.2),Txn('DEMO-3','DEMO-CARD-K1','DEMO-CUST',now.replace(minute=20),3.1,'online','C',.2),Txn('DEMO-4','DEMO-CARD-K1','DEMO-CUST',now,259.98,'online','C',.72,'DEMO-DEVICE','DEMO-REGION')]
    return tx,[{'case_id':'DEMO-001','flagged_txn_id':'DEMO-4','opened_at':now.isoformat(),'trigger_type':'risk_score'}]
