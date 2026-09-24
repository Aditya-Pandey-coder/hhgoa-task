from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json, os
app=FastAPI(title='HHGOA Tier A Backend')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173',os.getenv('FRONTEND_ORIGIN','http://localhost:5173')],allow_methods=['*'],allow_headers=['*'])
ROOT=Path(os.getenv('HHGOA_OUT','out'))
def read(path):
    try:return json.loads(path.read_text())
    except FileNotFoundError: raise HTTPException(404,'not found')
@app.get('/api/health')
def health(): return {'ok':True,'tigergraph':False,'llm':False,'mode':'static'}
@app.get('/api/cases')
def cases(): return read(ROOT/'index.json')
@app.get('/api/cases/{case_id}')
def case(case_id): return read(Path('cases')/(case_id+'.json'))
@app.get('/api/cases/{case_id}/trace')
def trace(case_id): return read(ROOT/'traces'/(case_id+'.trace.json'))
@app.get('/api/cases/{case_id}/graph')
def graph(case_id): return read(ROOT/'graphs'/(case_id+'.graph.json'))
@app.get('/api/metrics')
def metrics(): return read(ROOT/'metrics.json')
