#!/usr/bin/env python3
"""Apply mnemonics from new_mnemonics.json into words.json's m field.

new_mnemonics.json schema: {word_lowercase: mnemonic_text, ...}

Overwrites m field for matching words. Reports how many were applied,
how many words still missing a mnemonic, and any orphan keys not in
words.json.
"""
import json, os, sys

HERE = os.path.dirname(__file__)
WORDS = os.path.join(HERE, 'words.json')
NEW   = os.path.join(HERE, 'new_mnemonics.json')

with open(WORDS, encoding='utf-8') as f:
    words = json.load(f)
with open(NEW, encoding='utf-8') as f:
    new = json.load(f)

new_lower = {k.lower(): v for k, v in new.items()}
applied = 0
for w in words:
    key = w['w'].lower()
    if key in new_lower:
        w['m'] = new_lower[key]
        applied += 1

word_set = {w['w'].lower() for w in words}
orphans = [k for k in new_lower if k not in word_set]
missing = [w['w'] for w in words if not w.get('m')]

print(f'Applied: {applied} mnemonics')
print(f'Words still without a mnemonic: {len(missing)}')
if orphans:
    print(f'Orphan keys (in new_mnemonics.json but not words.json): {orphans[:10]}')

with open(WORDS, 'w', encoding='utf-8') as f:
    json.dump(words, f, ensure_ascii=False, indent=2)
print(f'Wrote {WORDS}')
