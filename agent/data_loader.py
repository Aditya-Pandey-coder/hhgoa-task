"""Input discovery and normalization for the supplied benchmark files."""
from __future__ import annotations
import csv, json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from .graph import Txn

ROOT_NAMES = ("data", "dataset", "input", ".")

def _files(kind):
    names = {
        "transactions": ("transactions.csv", "transactions.parquet", "transactions.json"),
        "identity": ("identity.csv", "identity.parquet", "identity.json"),
        "case_pack": ("case_pack.csv", "case_pack.json"),
        "closed": ("closed_cases_history.csv", "closed_cases_history.json"),
    }[kind]
    found=[]
    for root in ROOT_NAMES:
        base=Path(root)
        for name in names:
            p=base/name
            if p.exists() and p not in found: found.append(p)
    return found

def _rows(path):
    if path.suffix.lower()=='.json':
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,list) else list(value.values())
    if path.suffix.lower()=='.parquet':
        try:
            import pandas as pd
            return pd.read_parquet(path).to_dict('records')
        except Exception as exc:
            raise RuntimeError(f'Cannot read {path}; install pandas/pyarrow: {exc}') from exc
    with path.open(newline='', encoding='utf-8-sig') as fh: return list(csv.DictReader(fh))

def _get(row,*names,default=''):
    lowered={str(k).lower():v for k,v in row.items()}
    for n in names:
        v=lowered.get(n.lower())
        if v not in (None,''): return v
    return default

def _dt(value):
    try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).replace(tzinfo=None)
    except Exception: return datetime(2016,1,1)

def load_inputs():
    tx_file=next(iter(_files('transactions')),None); case_file=next(iter(_files('case_pack')),None)
    if not tx_file or not case_file:
        raise FileNotFoundError('Need transactions.csv/parquet/json and case_pack.csv/json under data/, dataset/, input/, or repository root')
    identity=[]
    identity_file=next(iter(_files('identity')),None)
    if identity_file:
        identity=[r for r in _rows(identity_file)]
    identity_by_id={str(_get(r,'TransactionID','transaction_id','txn_id')):r for r in identity}
    transactions=[]
    for r in _rows(tx_file):
        tid=str(_get(r,'TransactionID','transaction_id','txn_id'))
        ir=identity_by_id.get(tid,{})
        customer=str(_get(r,'customer_id','CustomerID',default='UNKNOWN-CUSTOMER'))
        card=str(_get(r,'card_id','card',default=f'{customer}-K1'))
        product=str(_get(r,'ProductCD','product',default='unknown'))
        channel=str(_get(r,'channel',default='in_person' if product=='W' else 'online'))
        device=' | '.join(str(_get(ir,n,default='')) for n in ('DeviceInfo','id_30','id_31','id_33')).strip(' |')
        transactions.append(Txn(tid,card,customer,_dt(_get(r,'ts','timestamp',default='2016-01-01')),float(_get(r,'TransactionAmt','amount',default=0) or 0),channel,product,float(_get(r,'risk_score',default=0) or 0),device,str(_get(r,'addr1','region',default='')),str(_get(r,'P_emaildomain','email',default=''))))
    cases=[]
    for r in _rows(case_file):
        cases.append({'case_id':str(_get(r,'case_id','id')), 'opened_at':str(_get(r,'opened_at',default='')), 'trigger_type':str(_get(r,'trigger_type',default='risk_score')), 'trigger_text':str(_get(r,'trigger_text',default='')), 'flagged_txn_id':str(_get(r,'flagged_txn_id','flagged_transaction_id','txn_id')), 'card_id':str(_get(r,'card_id',default='')), 'customer_id':str(_get(r,'customer_id',default='')), 'risk_score':_get(r,'risk_score',default='')})
    closed=[]
    closed_file=next(iter(_files('closed')),None)
    if closed_file: closed=_rows(closed_file)
    return transactions,cases,closed
