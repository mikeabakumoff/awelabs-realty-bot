# AweLabs Realty Bot

A Telegram sales assistant for a real estate agency. It answers property
questions in the visitor's language, narrows down what they are actually looking
for, offers matching listings from a live spreadsheet, and hands a captured lead
to a human.

The interesting part is not that it talks to an LLM. It is everything around
that call: what the model is allowed to say, how listings are chosen before the
prompt is built, what happens when someone tries to run up the bill, and how the
knowledge base improves itself overnight.

## What it does

- **Conversation in three languages** — Russian, English and Thai, detected per
  message rather than set once
- **Criteria extraction** — a separate model pass turns the running dialogue into
  a structured filter (budget, area, bedrooms, deal type) instead of hoping the
  main prompt remembers
- **Listing selection happens before the prompt** — the filter runs against the
  listings table in Python, and only a diverse sample of what survives is put in
  front of the model
- **Lead capture** — when a name and phone appear, the lead is stored and the
  owner is notified in Telegram
- **Visitor alerts** — a first-time visitor triggers a notification with their
  opening message
- **Nightly learning** — a scheduled pass reads the day's conversations and
  rewrites a knowledge file the bot loads on its next cycle

## Architecture notes

### The model is not the source of truth

Listings come from a Google Sheet, refreshed on a timer. Facts about the agency
come from `company.md`, a hand-edited file reloaded without a restart. Anything
absent from those two sources the bot is instructed to defer to a human rather
than invent — which is the whole reason the company file exists as a file and
not as prompt text.

Filtering also happens *before* the model sees anything. Criteria are extracted
from the dialogue, applied to the listings table in Python, and then a diverse
sample is taken to fit the prompt budget. Handing the model the whole table and
asking it to pick is the version of this that hallucinates addresses.

### Cost and abuse controls

Per-user rate limiting, daily message counts, and a running monthly spend total
checked against a budget ceiling. A public bot wired to a paid API without these
is a bill waiting to happen.

### Prompt versioning

The system prompt is assembled from parts — company facts, knowledge base,
filtered listings — and carries a version derived from its inputs, so a change
in behaviour can be traced to a change in what went in.

### Persistence

SQLite. Messages, leads, per-user counters and a small key/value table for
metadata. History is loaded per user with a turn limit, so context length stays
bounded regardless of how long someone has been chatting.

### Nightly learning loop

`learn.py` runs on a timer: it exports the day's dialogue corpus, sends it for
summarisation, and rewrites `knowledge.md`. The bot re-reads that file on its
next refresh cycle without restarting.

**`knowledge.md` is not in this repository.** It is generated from real visitor
conversations, and no word-level sanitisation can honestly guarantee it is clean,
so it is excluded rather than scrubbed. The code handles its absence — the
knowledge block is simply empty, and the bot runs on `company.md` and the
listings table alone.

## Layout

| File | |
|---|---|
| `realty_bot.py` | the bot: dialogue, filtering, prompt assembly, leads, limits |
| `learn.py` | nightly knowledge-base rebuild |
| `export_corpus.py` | dumps the dialogue corpus for that pass |
| `stats.py` | usage and spend reporting |
| `verify_listings.py` | asserts replies only ever offer listings that exist |
| `smoke_test.py` | end-to-end dialogue run without Telegram |
| `test_learning.py` | exercises the learning cycle |
| `company.md` | hand-edited facts the bot may state |

`verify_listings.py` is worth a second look: it is a guard against the failure
mode that matters most here — a confident reply describing a property that is
not in the table.

## Running it

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env      # then fill it in
venv/bin/python realty_bot.py
```

Configuration is entirely environment variables — see `.env.example` for the
four it needs. Nothing is read from anywhere else, and no key appears in code.

The listings sheet is read through a Google service account. The code expects
its credentials JSON at `secrets/sheets_credentials.json`; that file is not part
of this repository and the directory is gitignored.

## Deployment shape

Two systemd units: a service for the bot and a timer for the nightly learning
pass. The bot reloads listings, company facts and the knowledge base on its own
schedule, so routine content edits never require a restart.

## Stack

Python, python-telegram-bot, OpenAI API, SQLite, Google Sheets API.

The conversation runs on a small model (`gpt-4.1-mini`) — the work that makes
replies accurate happens in the filtering and prompt assembly around it, not in
model size. The nightly summarisation uses the larger `gpt-4.1`, since it runs
once a day and quality matters more than latency there.

---

*This repository is a sanitized copy. Runtime data — the conversation database,
the generated knowledge base, credentials and logs — is excluded by design.*
