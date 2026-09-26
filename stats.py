#!/usr/bin/env python3
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=7))
OWNER = None
try:
    for line in (BASE_DIR / ".env").read_text().splitlines():
        if line.startswith("REALTY_OWNER_CHAT_ID="):
            OWNER = line.split("=", 1)[1].strip()
except Exception:
    pass

conn = sqlite3.connect(BASE_DIR / "realty_bot.db")
conn.row_factory = sqlite3.Row


def who(uid, username, first_name):
    if OWNER and str(uid) == OWNER:
        return "вы"
    label = f"@{username}" if username else (first_name or "без ника")
    return label


def short(ts):
    return (ts or "")[:16].replace("T", " ")


if len(sys.argv) > 1:
    uid = int(sys.argv[1])
    rows = conn.execute(
        "SELECT * FROM messages WHERE user_id=? ORDER BY id", (uid,)
    ).fetchall()
    if not rows:
        print(f"диалогов с {uid} нет")
        raise SystemExit(0)
    head = rows[0]
    print(f"=== {uid} ({who(uid, head['username'], head['first_name'])}) ===\n")
    for r in rows:
        tag = "КЛИЕНТ" if r["role"] == "user" else "АНДРЕЙ"
        print(f"[{(r['created_at'] or '')[11:19]}] {tag}:")
        print("  " + (r["content"] or "").replace("\n", "\n  "))
        if r["role"] == "assistant" and r["input_tokens"]:
            print(f"  ({r['input_tokens']}/{r['output_tokens']} ток., "
                  f"{r['latency_ms']} мс, объекты: {r['offered_ids'] or '-'})")
        print()
    raise SystemExit(0)

print("=== ПОСЕТИТЕЛИ ===")
rows = conn.execute("""
    SELECT user_id,
           MAX(username)   AS username,
           MAX(first_name) AS first_name,
           COUNT(*)                AS total,
           SUM(role='user')        AS from_user,
           MIN(created_at)         AS first_seen,
           MAX(created_at)         AS last_seen,
           SUM(COALESCE(led_to_lead,0)) AS leads,
           SUM(COALESCE(input_tokens,0))  AS tok_in,
           SUM(COALESCE(output_tokens,0)) AS tok_out
      FROM messages GROUP BY user_id ORDER BY MAX(created_at) DESC""").fetchall()

if not rows:
    print("  пока никого")
for r in rows:
    cost = r["tok_in"] / 1e6 * 0.40 + r["tok_out"] / 1e6 * 1.60
    mark = " [ЗАЯВКА]" if r["leads"] else ""
    print(f"  {r['user_id']}  {who(r['user_id'], r['username'], r['first_name'])}{mark}")
    print(f"     реплик {r['total']} (от клиента {r['from_user']}), "
          f"{short(r['first_seen'])} -> {short(r['last_seen'])}, ${cost:.4f}")

print("\n=== ЗАЯВКИ ===")
leads = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20").fetchall()
if not leads:
    print("  нет")
for l in leads:
    print(f"  #{l['id']} {short(l['created_at'])}  {l['name']} / {l['phone']}"
          f"  @{l['username'] or '-'}")
    print(f"     {l['summary']}")

since = datetime.now(TZ).replace(day=1, hour=0, minute=0, second=0,
                                 microsecond=0).isoformat()
row = conn.execute(
    "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
    "FROM messages WHERE created_at>=?", (since,)).fetchone()
print(f"\n=== РАСХОД С 1 ЧИСЛА ===\n  "
      f"${row[0]/1e6*0.40 + row[1]/1e6*1.60:.4f}")
