#!/usr/bin/env python3
"""Generate mnemonics for 20 sample words to validate the new prompt.

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python3 sample_mnemonics.py
  python3 sample_mnemonics.py <api-key>

Picks a diverse mix: some easy, some medium, some hard. Prints to stdout —
nothing is written back to words.json yet.
"""
import json, sys, os, requests
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from generate_mnemonics import make_prompt, MODEL, MAX_TOKENS

API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ANTHROPIC_API_KEY', '')
if not API_KEY:
    print("Usage: ANTHROPIC_API_KEY=sk-ant-... python3 sample_mnemonics.py")
    sys.exit(1)

# A diverse spread: easy/common, medium GRE, harder GRE, and some that have
# historically been difficult to mnemonic well.
SAMPLE_WORDS = [
    'abandon', 'abate', 'abhor', 'aberrant',          # common openers
    'foible', 'serried', 'inaugurate', 'maculate',    # previously fixed by hand
    'malaise', 'penchant', 'spurious', 'bolster',     # known-anchor candidates
    'anthology', 'verdant', 'apophasis',              # tricky / no obvious 谐音
    'mendacious', 'sanctify', 'abscission',           # vivid-scene candidates
    'incessant', 'cajole',                            # to round out to 20
]

with open(os.path.join(os.path.dirname(__file__), 'words.json'), encoding='utf-8') as f:
    words = json.load(f)
by_w = {w['w']: w for w in words}

missing = [w for w in SAMPLE_WORDS if w not in by_w]
if missing:
    print(f'WARNING: not in words.json: {missing}')

HEADERS = {
    'Content-Type': 'application/json',
    'x-api-key': API_KEY,
    'anthropic-version': '2023-06-01',
}

def call(word):
    payload = {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'messages': [{'role': 'user', 'content': make_prompt(word)}]
    }
    resp = requests.post('https://api.anthropic.com/v1/messages',
                         headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()['content'][0]['text'].strip()

results = {}
with ThreadPoolExecutor(max_workers=6) as pool:
    futures = {pool.submit(call, by_w[w]): w for w in SAMPLE_WORDS if w in by_w}
    for fut in futures:
        w = futures[fut]
        try:
            results[w] = fut.result()
        except Exception as e:
            results[w] = f'[ERROR: {e}]'

# Print in original order
print('\n' + '=' * 70)
print('NEW MNEMONICS (sample of 20)')
print('=' * 70)
for w in SAMPLE_WORDS:
    if w not in results:
        continue
    entry = by_w[w]
    cn = '；'.join(k.get('cn', '') for k in entry.get('k', []) if k.get('cn'))
    print(f'\n— {w} ({cn}) —')
    print(results[w])
