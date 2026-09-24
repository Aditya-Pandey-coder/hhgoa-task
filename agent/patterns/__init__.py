"""Pattern detector entry points.

The scorer lives in ``agent.scorer``; this relative import keeps the package
importable when the runner is started from the repository root.
"""
from ..scorer import score_case


def detect(graph, flagged):
    result = score_case(graph, flagged)
    if result["pattern"] == "none" and result["verdict"] == "uncertain":
        if flagged.device_id and len(graph.device_neighbors(flagged.device_id)) > 1:
            result["pattern"] = "undocumented"
    return result


__all__ = ["detect"]
