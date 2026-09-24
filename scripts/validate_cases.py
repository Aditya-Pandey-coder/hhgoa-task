#!/usr/bin/env python3
import argparse,sys
from agent.validators import validate_paths
p=argparse.ArgumentParser(); p.add_argument('cases'); p.add_argument('out'); a=p.parse_args(); errors=validate_paths(a.cases,a.out)
if errors: print('\n'.join(errors)); sys.exit(1)
print('validation passed')
