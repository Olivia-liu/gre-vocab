# GRE单词 · 要你命3000

A mobile-first Progressive Web App for studying the GRE 要你命3000 vocabulary list. Optimized for iPhone, installable as a home screen app.

## Features

- **Spaced repetition** — cards cycle through New → Learning → Known based on your ratings (Again / Fuzzy / Got it)
- **AI mnemonics** — Claude-generated Chinese memory hooks for each word, with 谐音 (sound-alike) techniques where possible
- **Already know it** — mark words you already know as 已熟悉 to permanently skip them
- **Word list browser** — filter by status, search by keyword, A–Z index scrollbar for quick navigation
- **Multi-device sync** — optional token-based sync via Cloudflare KV; flags, custom mnemonics, and mastered words all merge across devices
- **Community flagging** — flag words whose mnemonics need improvement; flagged words are pooled across all users
- **Six color themes** — 初雪, 星际漫游, 茶馆午后, 钢笔墨水, 午夜电台, 桃子汽水
- **Offline support** — service worker caches all assets for fully offline use

## Stack

| Layer | Tech |
|---|---|
| Frontend | Vanilla HTML/CSS/JS, single `index.html` |
| Hosting | Vercel |
| Sync backend | Cloudflare Worker + KV |
| AI mnemonics | Claude API (Anthropic) |

## Project Structure

```
index.html          Main app — all UI and logic
words.json          Word data including mnemonics (single source of truth)
sw.js               Service worker for offline caching
manifest.json       PWA manifest
vercel.json         Cache-control headers for sw.js and index.html
generate_mnemonics.py   Script to generate mnemonics via Claude API
```

## words.json Format

Each entry in the array:

```json
{
  "w": "abrogate",
  "p": "v",
  "c": "废除，撤销",
  "e": "to abolish by authoritative action",
  "x": "abrogate a treaty 废除条约",
  "m": "「啊，不搞了(abrogate)！」把这条法律废了——abrogate，废除。"
}
```

| Field | Meaning |
|---|---|
| `w` | Word |
| `p` | Part of speech |
| `c` | Chinese definition |
| `e` | English definition |
| `x` | Example sentence (optional) |
| `m` | Mnemonic (optional) |

## Sync Backend

The Cloudflare Worker lives in `../gre-sync-worker/`. It exposes a simple REST API:

```
GET  /?token=<token>          Fetch progress data
PUT  /?token=<token>          Save progress data
GET  /?token=community_flagged   Fetch all community-flagged word indices
```

Extras (mnemonics, flagged words, mastered words) are stored under `<token>_extras` and merged — never overwritten — on pull.
