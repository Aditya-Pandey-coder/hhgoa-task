#!/usr/bin/env python3
import argparse,shutil
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('source'); ap.add_argument('destination'); a=ap.parse_args(); src=Path(a.source); dst=Path(a.destination); dst.mkdir(parents=True,exist_ok=True)
for p in src.rglob('*'):
    if p.is_file():
        q=dst/p.relative_to(src); q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
print(f'exported {src} to {dst}')
