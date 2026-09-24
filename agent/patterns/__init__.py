"""Pattern detector entry points.

The implementation is deliberately deterministic. The module re-exports the
scorer from the parent package; the previous version imported a non-existent
agent.patterns.scorer module, which caused `import agent.patterns` to fail.
"""
from ..scorer import score_case


def detect(graph, flagged):
    result = score_case(graph, flagged)
    if result["pattern"] == "none" and result["verdict"] == "uncertain":
        if flagged.device_id and len(graph.device_neighbors(flagged.device_id)) > 1:
            result["pattern"] = "undocumented"
    return result


__all__ = ["detect"]
