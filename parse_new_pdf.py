#!/usr/bin/env python3
"""
Parse 再要你命3000.pdf into structured JSON.

Format:
  word[IPA]
  【考法】 or 【考法N】 pos. 中文：english
  例 example_en chinese_translationǁmore_examples...
  近 syn1, syn2, syn3
  反 ant1, ant2 中文翻译
  派 derivatives

Output: book.json — list of word entries, each with one or more 考法.
"""

import fitz
import re
import json
import sys
import os
from collections import Counter

PDF_PATH   = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Downloads/再要你命3000.pdf')
OUTPUT     = os.path.join(os.path.dirname(__file__), 'book.json')

# Word content starts at page 20 (0-indexed: 19) — the "List 1" intro page
CONTENT_START_PAGE = 19


def extract_all_lines(doc):
    """Pull every line of text from the body of the book."""
    raw = []
    for pg_num in range(CONTENT_START_PAGE, len(doc)):
        text = doc[pg_num].get_text()
        for line in text.split('\n'):
            raw.append(line)
    return raw


def clean_lines(raw):
    """Strip whitespace, drop empty lines and structural headers."""
    cleaned = []
    for line in raw:
        line = line.rstrip()
        # Preserve leading whitespace check by stripping only trailing
        s = line.strip()
        if not s:
            continue
        # Skip List/Unit headers (single line like "List 1", "Unit 3")
        if re.match(r'^(List|Unit)\s*\d+\s*$', s):
            continue
        # Skip the bullet overview lines (e.g. "■ ABANDON  ■ ABASE  ...")
        if '■' in s:
            continue
        # Skip standalone page-number-like lines
        if re.match(r'^\d+\s*$', s):
            continue
        # Skip pipe-separated continuation of bullets
        if re.match(r'^[A-Z\-\s]+$', s) and len(s) < 80 and '■' not in s:
            # Could be a bullet continuation like "ADULTERATE" alone
            # but also could be wrong — keep it conservative
            continue
        cleaned.append(s)
    return cleaned


# Recognize: word[IPA] OR just word
# IPA brackets: fullwidth ［］ or halfwidth []
# Word: lowercase ASCII letters, possibly hyphenated, possibly two words separated by space
WORD_HEADER_RE = re.compile(
    r"""^
    ([a-z][a-z\-]*(?:\s[a-z]+)?)        # word (group 1)
    \s*
    (?:[\[［]([^\]］]*)[\]］])?           # optional IPA in [] or ［］ (group 2)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE
)

KAOFA_RE = re.compile(r'^【(?:考法|考点)(\d*)】\s*(.*)$')


def looks_like_word_header(line, has_pending_word):
    """Heuristic: is this line the start of a new word entry?"""
    m = WORD_HEADER_RE.match(line)
    if not m:
        return False, None, None
    word = m.group(1).lower()
    ipa = m.group(2) or ''
    # If IPA is present, definitely a word header
    if ipa:
        return True, word, ipa
    # No IPA — must be just a single short word
    # (continuation lines often start with English phrases too, so be careful)
    # Heuristic: single ASCII word, length 2-25 chars, no spaces
    if 2 <= len(word) <= 25 and ' ' not in word and '-' not in word:
        return True, word, ''
    # Two-word headwords (rare): e.g. "ad lib" — only accept if line is really short
    if 2 <= len(word) <= 25 and len(line) <= 25:
        return True, word, ''
    return False, None, None


def parse_kaofa_content(raw):
    """Parse the rest of a 【考法】 line into ipa, pos, cn, en."""
    raw = raw.strip()
    ipa = ''
    pos = ''
    # Optional leading IPA: ［...］ or [...]
    m_ipa = re.match(r'^[\[［]([^\]］]*)[\]］]\s*(.*)', raw, re.DOTALL)
    if m_ipa:
        ipa = m_ipa.group(1).strip()
        raw = m_ipa.group(2).strip()

    # POS: 1-5 ASCII letters with periods (n., v., adj., adv., vt., vi., ...)
    m_pos = re.match(r'^([a-zA-Z]{1,5}\.(?:[a-zA-Z]{1,4}\.)?)\s*(.*)', raw, re.DOTALL)
    if m_pos:
        pos_candidate = m_pos.group(1)
        # Sanity: short and ends in period
        if len(pos_candidate) <= 8:
            pos = pos_candidate
            raw = m_pos.group(2).strip()

    # Split Chinese : English on first colon (full or halfwidth)
    parts = re.split(r'[：:]', raw, maxsplit=1)
    if len(parts) == 2:
        cn = parts[0].strip()
        en = parts[1].strip()
    else:
        cn = raw.strip()
        en = ''

    return {'ipa': ipa, 'pos': pos, 'cn': cn, 'en': en}


def parse_examples_text(text):
    """Parse the text after 例 into a list of {en, cn} examples."""
    examples = []
    # Multiple examples separated by ǁ (U+01C1)
    for part in text.split('ǁ'):
        part = part.strip()
        if not part:
            continue
        # Find first CJK character to split English from Chinese translation
        en_end = len(part)
        for i, ch in enumerate(part):
            if ord(ch) >= 0x2E80:
                en_end = i
                break
        en = part[:en_end].strip()
        cn = part[en_end:].strip()
        examples.append({'en': en, 'cn': cn})
    return examples


def next_kaofa_distance(lines, idx):
    """Return how many lines forward until the next 【考法】 line, or -1.
    Used to validate word-header candidates without IPA: a real word header
    is always followed by a 【考法】 line on the next non-empty line."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        if KAOFA_RE.match(lines[j]):
            return j - idx
        # If we hit another section marker or punctuation-heavy line, give up
    return -1


def parse_book(pdf_path):
    doc = fitz.open(pdf_path)
    raw = extract_all_lines(doc)
    lines = clean_lines(raw)

    words = []
    current = None        # current word entry
    current_kaofa = None  # current 考法 dict
    current_section = None  # 'kaofa' | 'example' | 'syn' | 'ant' | 'der'

    def flush_kaofa():
        nonlocal current_kaofa
        if current_kaofa and current is not None:
            current['k'].append(current_kaofa)
        current_kaofa = None

    def flush_word():
        nonlocal current
        flush_kaofa()
        if current and current['k']:
            # Post-process: parse the raw kaofa strings
            for k in current['k']:
                parsed = parse_kaofa_content(k.pop('_raw', ''))
                # Merge: parsed POS/cn/en go into the kaofa; ipa goes there too
                # If word-level ipa is empty and 考法 has one, we leave both as-is
                # (a few words have per-考法 IPA when POS differs — keep at 考法 level)
                if parsed['ipa']:
                    k['ipa'] = parsed['ipa']
                k['pos'] = parsed['pos']
                k['cn'] = parsed['cn']
                k['en'] = parsed['en']
                # Parse examples
                if k.get('_examples_raw'):
                    parsed_examples = []
                    for raw_ex in k.pop('_examples_raw'):
                        parsed_examples.extend(parse_examples_text(raw_ex))
                    k['ex'] = parsed_examples
                else:
                    k.pop('_examples_raw', None)
                    k['ex'] = []
            words.append(current)
        current = None

    for idx, line in enumerate(lines):
        # 1. 考法 marker — must check before word header
        m = KAOFA_RE.match(line)
        if m:
            flush_kaofa()
            current_kaofa = {
                '_raw': m.group(2),
                '_examples_raw': [],
            }
            current_section = 'kaofa'
            continue

        # 2. Section markers (例, 近, 反, 派) — only valid inside a 考法
        if current_kaofa is not None and line and ord(line[0]) >= 0x2E80:
            ch = line[0]
            rest = line[1:].lstrip('　 \t')
            if ch == '例':
                current_kaofa['_examples_raw'].append(rest)
                current_section = 'example'
                continue
            if ch == '近':
                current_kaofa['syn'] = rest
                current_section = 'syn'
                continue
            if ch == '反':
                current_kaofa['ant'] = rest
                current_section = 'ant'
                continue
            if ch == '派':
                current_kaofa['der'] = rest
                current_section = 'der'
                continue

        # 3. Word header (only if line starts at left, all-ASCII, etc.)
        is_hdr, word, ipa = looks_like_word_header(line, current is not None)
        if is_hdr:
            # If no IPA, require 【考法】 on the IMMEDIATE next line.
            # Wrapped continuation words ('to', 'or', 'the', 'something') would
            # otherwise be misread as new word entries.
            if not ipa and next_kaofa_distance(lines, idx) != 1:
                # Treat as continuation, not a header
                pass
            else:
                flush_word()
                current = {'w': word, 'ipa': ipa, 'k': []}
                current_kaofa = None
                current_section = 'word'
                continue

        # 4. Continuation: append to whatever section we're in
        if current_kaofa is None:
            continue  # nothing to attach to (probably stray text between entries)

        # Join wrapped lines: insert a space if the previous content doesn't
        # end in a space and doesn't end at a CJK boundary (where spacing isn't
        # needed between Chinese chars).
        def _join(prev, nxt):
            if not prev:
                return nxt
            if prev.endswith((' ', '\t', '　')):
                return prev + nxt
            # No space needed if joining two CJK chars
            if ord(prev[-1]) >= 0x2E80 and nxt and ord(nxt[0]) >= 0x2E80:
                return prev + nxt
            return prev + ' ' + nxt

        if current_section == 'kaofa':
            current_kaofa['_raw'] = _join(current_kaofa.get('_raw', ''), line)
        elif current_section == 'example' and current_kaofa['_examples_raw']:
            current_kaofa['_examples_raw'][-1] = _join(current_kaofa['_examples_raw'][-1], line)
        elif current_section == 'syn':
            current_kaofa['syn'] = _join(current_kaofa.get('syn', ''), line)
        elif current_section == 'ant':
            current_kaofa['ant'] = _join(current_kaofa.get('ant', ''), line)
        elif current_section == 'der':
            current_kaofa['der'] = _join(current_kaofa.get('der', ''), line)

    flush_word()
    return words


def merge_duplicates(words):
    """If a word appears in multiple entries (book has supplementary section
    that re-lists some words), merge their 考法 lists into a single entry."""
    by_word = {}
    order = []
    for w in words:
        key = w['w']
        if key not in by_word:
            by_word[key] = w
            order.append(key)
        else:
            existing = by_word[key]
            # Append 考法 from this entry to the existing one, deduping by (pos, cn)
            existing_keys = {(k.get('pos',''), k.get('cn','')) for k in existing['k']}
            for k in w['k']:
                if (k.get('pos',''), k.get('cn','')) not in existing_keys:
                    existing['k'].append(k)
            # Prefer non-empty IPA
            if not existing['ipa'] and w['ipa']:
                existing['ipa'] = w['ipa']
    return [by_word[k] for k in order]


def main():
    print(f'Parsing: {PDF_PATH}')
    words = parse_book(PDF_PATH)
    print(f'Extracted {len(words)} word entries (raw)')
    words = merge_duplicates(words)
    print(f'After merging duplicates: {len(words)}')

    # Stats
    total_kaofa = sum(len(w['k']) for w in words)
    total_examples = sum(len(k.get('ex', [])) for w in words for k in w['k'])
    with_syn = sum(1 for w in words for k in w['k'] if k.get('syn'))
    with_ant = sum(1 for w in words for k in w['k'] if k.get('ant'))
    with_der = sum(1 for w in words for k in w['k'] if k.get('der'))

    print(f'  Total 考法: {total_kaofa}')
    print(f'  Total examples: {total_examples}')
    print(f'  With 近 (syn): {with_syn}')
    print(f'  With 反 (ant): {with_ant}')
    print(f'  With 派 (der): {with_der}')

    # Detect duplicates
    seen = Counter(w['w'] for w in words)
    dupes = [w for w, c in seen.items() if c > 1]
    print(f'  Duplicate words: {len(dupes)}')
    if dupes[:10]:
        print(f'    {dupes[:10]}')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f'\nWritten: {OUTPUT} ({size_kb:.0f} KB)')


if __name__ == '__main__':
    main()
