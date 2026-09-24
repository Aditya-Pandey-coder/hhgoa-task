"""Policy engine implementing exact action names and routes."""
ACTIONS=['ALLOW_TRANSACTION','DECLINE_TRANSACTION','MONITOR_CARD','MONITOR_CONNECTED_CARDS','WARN_CUSTOMER','VERIFY_WITH_CUSTOMER','STEP_UP_AUTH','BLOCK_CARD','BLOCK_ALL_CARDS','GENERATE_REPORT','CREATE_CASE','FILE_REPORT','ESCALATE_TO_ANALYST','CLOSE_NO_FRAUD']
ROUTES={'ALLOW_TRANSACTION':'auto','MONITOR_CARD':'auto','MONITOR_CONNECTED_CARDS':'auto','WARN_CUSTOMER':'auto','VERIFY_WITH_CUSTOMER':'auto','STEP_UP_AUTH':'auto','GENERATE_REPORT':'auto','CREATE_CASE':'auto','ESCALATE_TO_ANALYST':'auto','CLOSE_NO_FRAUD':'auto','DECLINE_TRANSACTION':'L1','BLOCK_ALL_CARDS':'L2','FILE_REPORT':'L2'}
def route(action,exposure): return 'L2' if action=='BLOCK_CARD' and exposure>2500 else 'L1' if action=='BLOCK_CARD' else ROUTES[action]
def recommend(s):
    out=[]; p=s.get('probability',0); v=s.get('verdict','uncertain'); response=s.get('customer_response')
    def add(a,r,why): out.append({'action':a,'route':route(a,s.get('exposure_usd',0)),'reason':f'{r}: {why}'})
    if response=='denies':
        if s.get('recurring_match'): add('CREATE_CASE','R7','disputed recurring charge'); add('VERIFY_WITH_CUSTOMER','R7','confirm recurring activity'); add('WARN_CUSTOMER','R7','recurring charge guidance')
        else: add('BLOCK_CARD','R2','customer denied transaction'); add('CREATE_CASE','R2','unauthorized activity reported')
    elif response=='confirms': add('CLOSE_NO_FRAUD','R3','customer confirmed transaction')
    elif response=='no_reply':
        add('MONITOR_CARD','R4','no reply within 24 hours'); add('DECLINE_TRANSACTION','R4','protect pending authorizations')
        if s.get('exposure_usd',0)>500: add('ESCALATE_TO_ANALYST','R8','exposure exceeds $500')
    elif s.get('testing'):
        add('DECLINE_TRANSACTION','R5','card testing sequence observed'); add('STEP_UP_AUTH','R5','authenticate after testing sequence')
        if s.get('cleared_purchase_over_100'): add('BLOCK_CARD','R5','purchase above $100 already cleared')
    elif v=='legitimate': add('CLOSE_NO_FRAUD','R3','activity assessed as legitimate')
    elif p>=.30: add('VERIFY_WITH_CUSTOMER','R1','weak or ambiguous signal requires verification')
    else: add('ALLOW_TRANSACTION','R1','low fraud probability')
    if p>=.30 and not any(x['action'] in ('CREATE_CASE','CLOSE_NO_FRAUD') for x in out): add('CREATE_CASE','3a','probability meets case threshold')
    shared=s.get('shared_element',False)
    if p>=.70 and (s.get('exposure_usd',0)>1000 or shared or s.get('pattern')=='undocumented'):
        add('FILE_REPORT','R6' if shared else 'R9' if s.get('pattern')=='undocumented' else '3a','report gate satisfied')
    if shared and p>=.70: add('MONITOR_CONNECTED_CARDS','R6','shared origin links other cards')
    if v=='uncertain' and (s.get('exposure_usd',0)>500 or s.get('conflict',False)): add('ESCALATE_TO_ANALYST','R8','uncertain exposed or conflicting evidence')
    if s.get('two_cards_confirmed_fraud') or s.get('credentials_compromised'): add('BLOCK_ALL_CARDS','R10','two cards confirmed fraud or credentials compromised')
    seen=set(); return [x for x in out if not (x['action'] in seen or seen.add(x['action']))]
