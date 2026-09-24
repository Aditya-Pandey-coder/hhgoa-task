"""Pure policy engine with exact contract vocabulary."""
ACTIONS=["ALLOW_TRANSACTION","DECLINE_TRANSACTION","MONITOR_CARD","MONITOR_CONNECTED_CARDS","WARN_CUSTOMER","VERIFY_WITH_CUSTOMER","STEP_UP_AUTH","BLOCK_CARD","BLOCK_ALL_CARDS","GENERATE_REPORT","CREATE_CASE","FILE_REPORT","ESCALATE_TO_ANALYST","CLOSE_NO_FRAUD"]
ROUTES={"ALLOW_TRANSACTION":"auto","MONITOR_CARD":"auto","MONITOR_CONNECTED_CARDS":"auto","WARN_CUSTOMER":"auto","VERIFY_WITH_CUSTOMER":"auto","STEP_UP_AUTH":"auto","GENERATE_REPORT":"auto","CREATE_CASE":"auto","ESCALATE_TO_ANALYST":"auto","CLOSE_NO_FRAUD":"auto","DECLINE_TRANSACTION":"L1","BLOCK_ALL_CARDS":"L2","FILE_REPORT":"L2"}

def recommend(s):
    out=[]
    def add(action, rule, reason): out.append({"action":action,"route":route(action,s.get("exposure_usd",0)),"reason":f"{rule}: {reason}"})
    p=s.get("probability",0); v=s.get("verdict","uncertain")
    if v=="legitimate": add("CLOSE_NO_FRAUD","R3","evidence supports legitimate activity")
    elif s.get("customer_response")=="denies" or v=="fraud":
        add("BLOCK_CARD","R2","fraud is confirmed or customer denied")
        add("CREATE_CASE","3a","fraud investigation requires a case")
    elif s.get("testing"):
        add("DECLINE_TRANSACTION","R5","testing sequence observed")
        add("STEP_UP_AUTH","R5","authenticate after testing sequence")
    elif p >= .30: add("VERIFY_WITH_CUSTOMER","R1","verify before blocking ambiguous activity")
    else: add("ALLOW_TRANSACTION","R1","low probability")
    if p >= .30 and not any(x["action"]=="CREATE_CASE" for x in out): add("CREATE_CASE","3a","probability meets case threshold")
    shared=s.get("shared_element",False)
    if p >= .70 and (s.get("exposure_usd",0)>1000 or shared or s.get("pattern")=="undocumented"):
        add("FILE_REPORT","R6" if shared else "R9" if s.get("pattern")=="undocumented" else "3a","report gate satisfied")
    if shared and p >= .70: add("MONITOR_CONNECTED_CARDS","R6","shared element links connected cards")
    if v=="uncertain" and (s.get("exposure_usd",0)>500 or s.get("conflict",False)): add("ESCALATE_TO_ANALYST","R8","uncertainty or conflict requires review")
    if s.get("two_cards_confirmed_fraud",False) and p>=.70: add("BLOCK_ALL_CARDS","R10","two cards confirmed fraudulent")
    seen=set(); return [x for x in out if not (x["action"] in seen or seen.add(x["action"]))]

def route(action, exposure):
    if action=="BLOCK_CARD": return "L2" if exposure>2500 else "L1"
    return ROUTES[action]
