#!/usr/bin/env python3
"""Build mnemonics.json from mn_data.py — one string per word index."""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mn_data import MN

with open(os.path.join(os.path.dirname(__file__), 'words.json'), encoding='utf-8') as f:
    words = json.load(f)

total = len(words)
out = [MN.get(i, '') for i in range(total)]

missing = sum(1 for m in out if not m)
print(f'Words: {total}  Covered: {total - missing}  Missing: {missing}')

dest = os.path.join(os.path.dirname(__file__), 'mnemonics.json')
with open(dest, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

kb = os.path.getsize(dest) / 1024
print(f'Written: mnemonics.json ({kb:.0f} KB)')
