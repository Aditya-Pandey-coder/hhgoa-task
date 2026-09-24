"""Input discovery and normalization for benchmark files."""
from __future__ import annotations
import csv,json
from datetime import datetime
from pathlib import Path
from .graph import Txn

ROOTS=(Path("data"),Path("dataset"),Path("input"),Path("."))
def _find(names):
    for root in ROOTS:
        for name in names:
            p=root/name
            if p.exists() and p.is_file(): return p
    return None
def _rows(path):
    if path.suffix.lower()=='.json':
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,list) else list(value.values())
    if path.suffix.lower()=='.parquet':
        try:
            import pandas as pd
            return pd.read_parquet(path).to_dict('records')
        except Exception as exc: raise RuntimeError(f"Install pandas and pyarrow to read {path}: {exc}") from exc
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def _get(r,*names,default=''):
    d={str(k).lower():v for k,v in r.items()}
    for n in names:
        v=d.get(n.lower())
        if v not in (None,''): return v
    return default
def _float(v,default=0.0):
    try: return float(v)
    except (TypeError,ValueError): return default
def _dt(v):
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00')).replace(tzinfo=None)
    except (TypeError,ValueError): return datetime(2016,1,1)
def load_inputs():
    txp=_find(('transactions.csv','transactions.parquet','transactions.json')); cp=_find(('case_pack.csv','case_pack.json'))
    if not txp or not cp: raise FileNotFoundError('Missing transactions and/or case_pack input')
    ip=_find(('identity.csv','identity.parquet','identity.json')); identity={}
    if ip: identity={str(_get(r,'TransactionID','transaction_id','txn_id')):r for r in _rows(ip)}
    tx=[]
    for r in _rows(txp):
        tid=str(_get(r,'TransactionID','transaction_id','txn_id')); ir=identity.get(tid,{})
        customer=str(_get(r,'customer_id','CustomerID',default='UNKNOWN-CUSTOMER'))
        card=str(_get(r,'card_id',default=f'{customer}-K1'))
        product=str(_get(r,'ProductCD','product',default='unknown')); channel=str(_get(r,'channel',default='in_person' if product=='W' else 'online'))
        parts=[str(_get(ir,n,default='')) for n in ('DeviceInfo','id_30','id_31','id_33')]; label=' | '.join(x for x in parts if x)
        tx.append(Txn(tid,card,customer,_dt(_get(r,'ts','timestamp',default='2016-01-01')),_float(_get(r,'TransactionAmt','amount')),
          channel,product,_float(_get(r,'risk_score')),label,str(_get(r,'addr1','region',default='')),str(_get(r,'P_emaildomain','email',default='')),label))
    cases=[]
    for r in _rows(cp):
        cases.append({'case_id':str(_get(r,'case_id','id')),'opened_at':str(_get(r,'opened_at')),'trigger_type':str(_get(r,'trigger_type',default='risk_score')),'trigger_text':str(_get(r,'trigger_text')),'flagged_txn_id':str(_get(r,'flagged_txn_id','flagged_transaction_id','txn_id')),'card_id':str(_get(r,'card_id')),'customer_id':str(_get(r,'customer_id')),'risk_score':_get(r,'risk_score')})
    closedp=_find(('closed_cases_history.csv','closed_cases_history.parquet','closed_cases_history.json'))
    return tx,cases,(_rows(closedp) if closedp else [])
