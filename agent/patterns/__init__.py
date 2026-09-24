from .scorer import score_case

def detect(graph, flagged):
    result=score_case(graph, flagged)
    if result["pattern"] == "none" and result["verdict"] == "uncertain":
        result["pattern"]="undocumented" if flagged.device_id and len(graph.device_neighbors(flagged.device_id)) > 1 else "none"
    return result
