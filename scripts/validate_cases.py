#!/usr/bin/env python3
"""Validate generated case files and their traces."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
from agent.validators import validate_paths

parser = argparse.ArgumentParser()
parser.add_argument("cases")
parser.add_argument("out")
args = parser.parse_args()
errors = validate_paths(args.cases, args.out)
if errors:
    print("\n".join(errors))
    raise SystemExit(1)
print("validation passed")
