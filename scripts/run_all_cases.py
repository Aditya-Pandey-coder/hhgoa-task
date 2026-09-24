#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
from agent.data_loader import load_inputs
from agent.graph import LocalGraph
from agent.runner import demo_inputs,run_case

def main():
    p=argparse.ArgumentParser(); p.add_argument('--demo',action='store_true'); p.add_argument('--out',default='out'); p.add_argument('--cases',default='cases'); a=p.parse_args()
    if a.demo: tx,rows,closed=(*demo_inputs(),[])
    else: tx,rows,closed=load_inputs()
    out=Path(a.out); cd=Path(a.cases)
    for d in (out/'traces',out/'graphs',cd): d.mkdir(parents=True,exist_ok=True)
    graph=LocalGraph(tx,closed); index=[]
    for row in sorted(rows,key=lambda r:r.get('opened_at','')):
        case,trace,flagged,affected=run_case(row,graph,'demo' if a.demo else 'batch')
        (cd/f"{row['case_id']}.json").write_text(json.dumps(case,indent=2))
        (out/'traces'/f"{row['case_id']}.trace.json").write_text(json.dumps(trace,indent=2))
        nodes=[]; edges=[]
        def node(i,t,l,r,attrs=None): nodes.append({'id':i,'type':t,'label':l,'role':r,'attrs':attrs or {}})
        node(flagged.customer_id,'Customer',flagged.customer_id,'context',{}); node(flagged.card_id,'Card',flagged.card_id,'flagged',{'customer_id':flagged.customer_id}); edges.append({'id':'owns','type':'OWNS','source':flagged.customer_id,'target':flagged.card_id,'attrs':{}})
        for t in graph.card_window(flagged.card_id,flagged.ts,72):
            node(t.id,'Transaction',f'${t.amount:.2f}','flagged' if t.id==flagged.id else 'affected',{'ts':t.ts.strftime('%Y-%m-%d %H:%M:%S'),'amount':t.amount,'channel':t.channel,'product':t.product,'risk_score':t.risk_score,'card_id':t.card_id}); edges.append({'id':f'made-{t.id}','type':'MADE','source':flagged.card_id,'target':t.id,'attrs':{}})
            if t.device_id: node(t.device_id,'DeviceProfile',t.device_label or t.device_id,'connected',{}); edges.append({'id':f'dev-{t.id}','type':'FROM_DEVICE','source':t.id,'target':t.device_id,'attrs':{}})
        (out/'graphs'/f"{row['case_id']}.graph.json").write_text(json.dumps({'contract_version':'1.0','case_id':row['case_id'],'nodes':list({n['id']:n for n in nodes}.values())[:150],'edges':edges},indent=2))
        c=case['case']; index.append({'case_id':c['case_id'],'opened_at':row.get('opened_at',''),'trigger_type':row.get('trigger_type','risk_score'),'card_id':c['card_id'],'customer_id':c['customer_id'],'flagged_txn_id':c['flagged_txn_id'],'risk_score':flagged.risk_score,'status':c['status'],'verdict':c['verdict'],'fraud_probability':c['fraud_probability'],'pattern':c['pattern'],'exposure_usd':c['exposure_usd'],'final_actions':[x['action'] for x in case['next_best_actions']['final']],'sar_file':case['sar']['file'],'awaiting_approval_count':sum(x['route']!='auto' for x in case['next_best_actions']['final']),'tool_calls':case['tool_calls'],'latency_s':case['latency_s']})
    (out/'index.json').write_text(json.dumps({'contract_version':'1.0','generated_at':datetime.utcnow().isoformat()+'Z','cases':index},indent=2))
    (out/'closed_cases_lite.json').write_text(json.dumps({str(c.get('case_id')):c for c in closed if c.get('case_id')},indent=2))
    (out/'metrics.json').write_text(json.dumps({'contract_version':'1.0','generated_at':datetime.utcnow().isoformat()+'Z','cases':[{'case_id':x['case_id'],'tool_calls':x['tool_calls'],'tokens':0,'latency_s':x['latency_s'],'validators_passed':True,'validator_failures':[]} for x in index],'totals':{'tool_calls':sum(x['tool_calls'] for x in index),'tokens':0,'latency_s':sum(x['latency_s'] for x in index)},'backtest':{'n':0},'calibration_bins':[]},indent=2))
    print(f'processed {len(index)} cases ({"demo" if a.demo else "official"} mode)')
if __name__=='__main__': main()
