"""Pure policy engine with exact contract vocabulary."""
ACTIONS=["ALLOW_TRANSACTION","DECLINE_TRANSACTION","MONITOR_CARD","MONITOR_CONNECTED_CARDS","WARN_CUSTOMER","VERIFY_WITH_CUSTOMER","STEP_UP_AUTH","BLOCK_CARD","BLOCK_ALL_CARDS","GENERATE_REPORT","CREATE_CASE","CLOSE_NO_FRAUD","FILE_REPORT","ESCALATE_TO_ANALYST"]
ROUTES={"ALLOW_TRANSACTION":"auto","MONITOR_CARD":"auto","MONITOR_CONNECTED_CARDS":"auto","WARN_CUSTOMER":"auto","VERIFY_WITH_CUSTOMER":"auto","STEP_UP_AUTH":"auto","GENERATE_REPORT":"auto","CREATE_CASE":"auto","CLOSE_NO_FRAUD":"auto","FILE_REPORT":"auto","ESCALATE_TO_ANALYST":"auto","BLOCK_CARD":"L1","BLOCK_ALL_CARDS":"L2"}

def route(action, exposure):
    if action == "BLOCK_CARD":
        return "L2" if exposure > 2500 else "L1"
    return ROUTES[action]

def recommend(s):
    out=[]
    def add(action, rule, reason):
        out.append({"action": action, "route": route(action, s.get("exposure_usd", 0)), "reason": f"{rule}: {reason}"})

    p = s.get("probability", 0)
    v = s.get("verdict", "uncertain")
    response = s.get("customer_response")

    if response == "denies" or v == "fraud":
        add("BLOCK_CARD", "R2", "customer denied or fraud is confirmed")
        add("CREATE_CASE", "3a", "fraud investigation requires a case")
    elif response == "confirms":
        add("CLOSE_NO_FRAUD", "R3", "customer confirmed the transaction")
    elif response == "no_reply":
        add("MONITOR_CARD", "R4", "no reply within 24 hours")
        add("DECLINE_TRANSACTION", "R4", "protect pending authorizations")
        if s.get("exposure_usd", 0) > 500:
            add("ESCALATE_TO_ANALYST", "R8", "exposure exceeds $500")
    elif s.get("testing"):
        add("DECLINE_TRANSACTION", "R5", "testing sequence observed")
        add("STEP_UP_AUTH", "R5", "authenticate after testing sequence")
    elif v == "legitimate":
        add("CLOSE_NO_FRAUD", "R3", "activity assessed as legitimate")
    elif p >= 0.30:
        add("VERIFY_WITH_CUSTOMER", "R1", "weak or ambiguous signal requires verification")
    else:
        add("ALLOW_TRANSACTION", "R1", "low fraud probability")

    if p >= 0.30 and not any(x["action"] in ("CREATE_CASE", "CLOSE_NO_FRAUD") for x in out):
        add("CREATE_CASE", "3a", "probability meets case threshold")

    shared = s.get("shared_element", False)
    if p >= 0.70 and (s.get("exposure_usd", 0) > 1000 or shared or s.get("pattern") == "undocumented"):
        add("FILE_REPORT", "R6" if shared else "R9" if s.get("pattern") == "undocumented" else "3a", "report gate satisfied")
    if shared and p >= 0.70:
        add("MONITOR_CONNECTED_CARDS", "R6", "shared origin links other cards")
    if v == "uncertain" and (s.get("exposure_usd", 0) > 500 or s.get("conflict", False)):
        add("ESCALATE_TO_ANALYST", "R8", "uncertain and exposed/conflicting evidence")
    if s.get("two_cards_confirmed_fraud") or s.get("credentials_compromised"):
        add("BLOCK_ALL_CARDS", "R10", "two cards confirmed fraud or credentials compromised")

    seen = set()
    return [x for x in out if not (x["action"] in seen or seen.add(x["action"]))]
