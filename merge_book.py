#!/usr/bin/env python3
"""
Merge book.json (parsed from 再要你命3000.pdf) into words.json.

Rules:
  - Word in both: take book content, preserve m (mnemonic) from words.json
  - Word only in words.json: keep as-is (PDF doesn't cover it)
  - Word only in book.json: add it (mnemonic empty)

Output schema (per entry):
  w     word
  ipa   IPA pronunciation (optional)
  k     [{pos, cn, en, ex:[{en,cn}], syn, ant, der}]  -- one or more 考法
  m     mnemonic (preserved)
"""

import json
import os
import sys

WORDS_FILE = os.path.join(os.path.dirname(__file__), 'words.json')
BOOK_FILE  = os.path.join(os.path.dirname(__file__), 'book.json')
OUT_FILE   = WORDS_FILE  # overwrite words.json
DRY_RUN    = '--dry-run' in sys.argv


def main():
    with open(WORDS_FILE, encoding='utf-8') as f:
        old_words = json.load(f)
    with open(BOOK_FILE, encoding='utf-8') as f:
        book = json.load(f)

    # Index by lowercase word
    book_by_w = {w['w'].lower(): w for w in book}
    old_by_w  = {w['w'].lower(): w for w in old_words}

    merged = []
    keep_old_word_order = True

    # Stats
    replaced = 0   # word in both -> use book content
    kept     = 0   # word only in old -> kept
    added    = 0   # word only in book -> added

    seen = set()

    if keep_old_word_order:
        # Walk old words first, in order; replace if book has them
        for old in old_words:
            key = old['w'].lower()
            if key in book_by_w:
                bk = book_by_w[key]
                merged.append({
                    'w':   bk['w'],
                    'ipa': bk.get('ipa', ''),
                    'k':   bk['k'],
                    'm':   old.get('m', ''),  # preserve mnemonic
                })
                replaced += 1
            else:
                # Word not in book — preserve old structure but normalize
                merged.append({
                    'w':   old['w'],
                    'ipa': '',
                    'k':   [{
                        'pos': old.get('p', ''),
                        'cn':  old.get('c', ''),
                        'en':  old.get('e', ''),
                        'ex':  [],
                        'syn': '',
                        'ant': '',
                    }],
                    'm':   old.get('m', ''),
                })
                # Migrate any old example sentence into new ex format
                if old.get('x'):
                    # Old x is "english chinese" — reuse the example splitter
                    x = old['x'].strip()
                    en_end = len(x)
                    for i, ch in enumerate(x):
                        if ord(ch) >= 0x2E80:
                            en_end = i
                            break
                    merged[-1]['k'][0]['ex'] = [{
                        'en': x[:en_end].strip(),
                        'cn': x[en_end:].strip(),
                    }]
                kept += 1
            seen.add(key)

        # Append words that exist only in book (not in old words.json)
        for bk in book:
            if bk['w'].lower() not in seen:
                merged.append({
                    'w':   bk['w'],
                    'ipa': bk.get('ipa', ''),
                    'k':   bk['k'],
                    'm':   '',
                })
                added += 1

    print(f'Old words.json:  {len(old_words)}')
    print(f'Book entries:    {len(book)}')
    print(f'')
    print(f'Replaced (word in both, use book + keep mnemonic): {replaced}')
    print(f'Kept old (word only in words.json):                {kept}')
    print(f'Added new (word only in book):                     {added}')
    print(f'Total merged: {len(merged)}')

    # Stats on mnemonics
    with_mn = sum(1 for w in merged if w.get('m'))
    print(f'\nWith mnemonics: {with_mn} / {len(merged)}')

    if DRY_RUN:
        print('\n[DRY RUN — not writing]')
        return

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(OUT_FILE) / 1024
    print(f'\nWritten: {OUT_FILE} ({size_kb:.0f} KB)')


if __name__ == '__main__':
    main()
