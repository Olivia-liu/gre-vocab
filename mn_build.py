#!/usr/bin/env python3
"""Write mnemonics from mn_data.py into words.json m field."""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from mn_data import MN

words_path = os.path.join(os.path.dirname(__file__), 'words.json')
with open(words_path, encoding='utf-8') as f:
    words = json.load(f)

covered = 0
for i, w in enumerate(words):
    if i in MN and MN[i]:
        w['m'] = MN[i]
        covered += 1

missing = len(words) - covered
print(f'Words: {len(words)}  Covered: {covered}  Missing: {missing}')

with open(words_path, 'w', encoding='utf-8') as f:
    json.dump(words, f, ensure_ascii=False, indent=2)

kb = os.path.getsize(words_path) / 1024
print(f'Written: words.json ({kb:.0f} KB)')
