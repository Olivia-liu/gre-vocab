#!/usr/bin/env python3
"""
批量为3000个GRE单词生成AI联想记忆法
用法: python3 generate_mnemonics.py <your-api-key>
      或设置环境变量 ANTHROPIC_API_KEY

- 并发10个请求，自动限速
- 增量保存，中断后重新运行只生成未完成的词
- 完成后写入 words.json 的 m 字段
"""

import json
import sys
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ── Config ───────────────────────────────────────────────────
WORDS_FILE    = os.path.join(os.path.dirname(__file__), 'words.json')
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), 'mnemonics_progress.json')

MODEL        = 'claude-haiku-4-5-20251001'
MAX_TOKENS   = 280
CONCURRENCY  = 8   # parallel requests
RETRY_LIMIT  = 3
RETRY_DELAY  = 5   # seconds between retries
# ─────────────────────────────────────────────────────────────

API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ANTHROPIC_API_KEY', '')
if not API_KEY:
    print("用法: python3 generate_mnemonics.py <your-anthropic-api-key>")
    print("或:   ANTHROPIC_API_KEY=sk-ant-... python3 generate_mnemonics.py")
    sys.exit(1)

HEADERS = {
    'Content-Type': 'application/json',
    'x-api-key': API_KEY,
    'anthropic-version': '2023-06-01',
}

def make_prompt(word):
    pos = word.get('p', '')
    cn  = word.get('c', '')
    en  = word.get('e', '')
    meaning = cn or en
    return f"""你是专门帮中国学生记GRE单词的记忆大师，擅长创作让人忍不住笑的联想记忆。

单词：{word['w']}（{pos + '.  ' if pos else ''}{meaning}）

请创作一个极其有趣、难以忘记的中文联想记忆法。你可以用以下方式：
🔊 谐音梗：这个词读起来像什么中文词或句子？
🖼️ 夸张画面：荒诞、视觉冲击强的场景
😂 搞笑故事：两三句傻乎乎但好记的故事
🧩 词形拆解：把单词拆成像中文读音的片段

要求：越荒诞夸张越好；不超过3句话；直接给联想，无需任何前言。"""

def call_api(word, idx):
    """Call Claude API for one word. Returns (idx, mnemonic_str) or raises."""
    payload = {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'messages': [{'role': 'user', 'content': make_prompt(word)}]
    }
    for attempt in range(RETRY_LIMIT):
        try:
            resp = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=HEADERS,
                json=payload,
                timeout=30
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get('retry-after', RETRY_DELAY * (attempt + 1)))
                print(f"  ⏳ 限速，等待 {wait}s…")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            text = data['content'][0]['text'].strip()
            return (idx, text)
        except requests.exceptions.Timeout:
            if attempt < RETRY_LIMIT - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise
    raise RuntimeError(f"Failed after {RETRY_LIMIT} attempts")

def main():
    # Load words
    with open(WORDS_FILE, encoding='utf-8') as f:
        words = json.load(f)
    total = len(words)
    print(f"共 {total} 个单词")

    # Load existing progress
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            progress = json.load(f)
        print(f"已有 {len(progress)} 个缓存，继续未完成的词…")

    # Figure out what's left
    todo = [(i, w) for i, w in enumerate(words) if str(i) not in progress]
    print(f"待生成：{len(todo)} 个")
    if not todo:
        print("全部已完成！")
    else:
        # Estimate cost
        est_input  = len(todo) * 220 / 1_000_000
        est_output = len(todo) * 120 / 1_000_000
        est_cost   = est_input * 0.80 + est_output * 4.00
        print(f"预计费用：约 ${est_cost:.2f} USD")
        print()

    save_lock = Lock()
    done_count = [len(progress)]

    def save_progress():
        with save_lock:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False)

    start = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(call_api, w, i): (i, w) for i, w in todo}
        for future in as_completed(futures):
            i, w = futures[future]
            try:
                idx, mnemonic = future.result()
                with save_lock:
                    progress[str(idx)] = mnemonic
                done_count[0] += 1
                pct = done_count[0] / total * 100
                elapsed = time.time() - start
                rate = (done_count[0] - len(progress) + len(todo) - len(todo)) / max(elapsed, 1)
                # simpler: words per second
                words_done_this_run = done_count[0] - (len(progress) - len(todo))
                rate2 = words_done_this_run / max(elapsed, 1)
                remaining = (total - done_count[0]) / max(rate2, 0.01)
                print(f"[{done_count[0]:4d}/{total}] {pct:5.1f}%  {w['w']:<20s}  剩余≈{remaining/60:.1f}分钟")
                # Save every 20 words
                if done_count[0] % 20 == 0:
                    save_progress()
            except Exception as e:
                print(f"  ❌ 失败 [{i}] {w['w']}: {e}")
                with save_lock:
                    progress[str(i)] = f"[生成失败: {w.get('c', '')}]"
                done_count[0] += 1

    # Final save of progress
    save_progress()

    # Write results into words.json m field
    failed = sum(1 for v in progress.values() if v.startswith('[生成失败'))
    empty  = sum(1 for i in range(total) if not progress.get(str(i)))

    for i, w in enumerate(words):
        m = progress.get(str(i), '')
        if m and not m.startswith('[生成失败'):
            w['m'] = m

    with open(WORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(WORDS_FILE) / 1024
    elapsed = time.time() - start
    print()
    print(f"✅ 完成！用时 {elapsed/60:.1f} 分钟")
    print(f"   成功: {total - failed - empty} / {total}")
    print(f"   失败: {failed}，空缺: {empty}")
    print(f"   文件: words.json ({size_kb:.0f} KB)")

if __name__ == '__main__':
    main()
