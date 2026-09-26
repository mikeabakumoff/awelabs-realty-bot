#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "realty_bot.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

users = [r[0] for r in conn.execute("SELECT DISTINCT user_id FROM messages ORDER BY user_id")]
for uid in users:
    turns = [dict(r) for r in conn.execute(
        "SELECT role, content, created_at, lang, model, prompt_version, "
        "input_tokens, output_tokens, latency_ms, offered_ids, led_to_lead "
        "FROM messages WHERE user_id=? ORDER BY id", (uid,))]
    if not turns:
        continue
    print(json.dumps({
        "dialog_id": uid,
        "turns": turns,
        "n_turns": len(turns),
        "got_lead": any(t.get("led_to_lead") for t in turns),
        "langs": sorted({t["lang"] for t in turns if t.get("lang")}),
    }, ensure_ascii=False))
print(f"диалогов: {len(users)}", file=sys.stderr)
