#!/usr/bin/env python3
import argparse,sys
from agent.validators import validate_paths
ap=argparse.ArgumentParser(); ap.add_argument('cases'); ap.add_argument('out'); args=ap.parse_args(); errors=validate_paths(args.cases,args.out)
if errors:
    print('\n'.join(errors)); sys.exit(1)
print('validation passed')
