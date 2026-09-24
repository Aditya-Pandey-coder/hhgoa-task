def test_policy_import():
    from agent.policy_engine import recommend
    out=recommend({'probability':.8,'verdict':'fraud','exposure_usd':100,'shared_element':False})
    assert out[0]['action']=='BLOCK_CARD'
    assert out[0]['route']=='L1'

def test_demo_generation(tmp_path):
    from agent.runner import demo_inputs,run_case
    from agent.graph import LocalGraph
    tx,rows=demo_inputs(); case,trace,_,_=run_case(rows[0],LocalGraph(tx),'demo')
    assert case['contract_version']=='1.0'
    assert case['case']['exposure_usd'] > 0
    assert trace['events'][-1]['kind']=='case_written'
