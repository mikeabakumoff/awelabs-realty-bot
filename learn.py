#!/usr/bin/env python3
import os
import sys
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "realty_bot.db"
KNOWLEDGE_PATH = BASE_DIR / "knowledge.md"


MODEL = "gpt-4.1"
MAX_TOKENS = 8000
TZ = timezone(timedelta(hours=7))


MIN_NEW_MESSAGES = 10

MAX_DIALOGS = 60
KNOWLEDGE_LIMIT_CHARS = 6000

DASHES = {"—": "-", "–": "-", "‒": "-", "−": "-", "―": "-"}


def short_dashes(text):
    for bad, good in DASHES.items():
        text = text.replace(bad, good)
    return text


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    return conn


def meta_get(conn, k, default=None):
    row = conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return row[0] if row else default


def meta_set(conn, k, v):
    conn.execute(
        "INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (k, str(v)),
    )
    conn.commit()


def collect_dialogs(conn, since_id):
    rows = conn.execute(
        "SELECT id, user_id, role, content, created_at, led_to_lead "
        "FROM messages WHERE id > ? ORDER BY id",
        (since_id,),
    ).fetchall()
    if not rows:
        return "", since_id, 0

    max_id = rows[-1][0]
    users = []
    for _, uid, *_ in rows:
        if uid not in users:
            users.append(uid)
    users = users[:MAX_DIALOGS]

    blocks = []
    for i, uid in enumerate(users, 1):
        turns = conn.execute(
            "SELECT role, content, led_to_lead FROM messages "
            "WHERE user_id=? ORDER BY id",
            (uid,),
        ).fetchall()
        got_lead = any(t[2] for t in turns)
        lines = [f"### Диалог {i} (заявка: {'да' if got_lead else 'нет'})"]
        for role, content, _ in turns:
            who = "Клиент" if role == "user" else "Андрей"
            lines.append(f"{who}: {content}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks), max_id, len(rows)


INSTRUCTION = """\
Ты помогаешь улучшать работу Андрея - ИИ-менеджера агентства недвижимости \
в Паттайе, который общается с клиентами в Telegram.

Ниже: текущая выжимка опыта (может быть пустой) и свежие диалоги. Обнови \
выжимку так, чтобы Андрей отвечал лучше в следующий раз.

Что должно попасть в выжимку:
1. ЧАСТЫЕ ВОПРОСЫ - о чём клиенты спрашивают регулярно (визы, налоги, \
   рассрочка, содержание, аренда под сдачу, районы). Записывай САМ ВОПРОС и \
   то, как на него лучше заходить, но НЕ фиксируй фактические ответы как \
   истину: Андрей мог назвать эти цифры и условия наугад, никто их не \
   проверял. Формулируй так: «спрашивают про X - честно сказать, что точные \
   условия уточнит менеджер». Любые конкретные суммы, ставки и названия \
   проектов с рассрочкой из ответов Андрея не переноси.
2. ВОЗРАЖЕНИЯ - на что жалуются и что останавливает от заявки.
3. ЧТО СРАБОТАЛО - формулировки и ходы, после которых клиент оставил \
   контакты. Смотри на пометку «заявка: да».
4. ЧТО НЕ СРАБОТАЛО - где разговор заглох, диалоги с пометкой «заявка: нет».
5. ПРОБЕЛЫ В БАЗЕ - что клиенты искали, а подходящего не нашлось \
   (район, бюджет, тип). Это заказчику полезнее всего.

Правила:
- Пиши по-русски, сжато, тезисами. Без вступлений и без выводов о себе.
- Не выдумывай: только то, что реально видно в диалогах.
- Не сохраняй персональные данные: ни имён, ни телефонов, ни username.
- Старое из выжимки не выбрасывай без причины, дополняй и уточняй.
- Уложись в {limit} символов. Если не влезает, оставь самое частотное.
- Не используй длинное тире, только обычный дефис.
- Верни ТОЛЬКО готовый текст выжимки, без markdown-заголовка верхнего уровня \
  и без комментариев о том, что ты сделал.

=== ТЕКУЩАЯ ВЫЖИМКА ===
{current}

=== СВЕЖИЕ ДИАЛОГИ ===
{dialogs}
"""


def main():
    dry = "--dry" in sys.argv

    if not os.environ.get("OPENAI_API_KEY"):
        print("[learn] нет OPENAI_API_KEY", file=sys.stderr)
        return 1

    conn = db()
    since_id = int(meta_get(conn, "learn_last_message_id", 0))
    dialogs, max_id, n_new = collect_dialogs(conn, since_id)

    if n_new < MIN_NEW_MESSAGES:
        print(f"[learn] новых реплик {n_new} (нужно {MIN_NEW_MESSAGES}) - пропускаю")
        return 0

    try:
        current = KNOWLEDGE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        current = ""

    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": INSTRUCTION.format(
                limit=KNOWLEDGE_LIMIT_CHARS,
                current=current or "(пусто, это первый прогон)",
                dialogs=dialogs,
            ),
        }],
    )

    finish = resp.choices[0].finish_reason
    if finish not in ("stop", "length"):
        print(f"[learn] неожиданное завершение: {finish}", file=sys.stderr)
        return 1

    text = short_dashes((resp.choices[0].message.content or "").strip())
    if not text:
        print("[learn] пустой ответ модели", file=sys.stderr)
        return 1
    text = text[:KNOWLEDGE_LIMIT_CHARS]

    if dry:
        print("=== ВЫЖИМКА (--dry, не сохраняю) ===")
        print(text)
        return 0

    if KNOWLEDGE_PATH.exists():
        stamp = datetime.now(TZ).strftime("%Y%m%d")
        KNOWLEDGE_PATH.replace(KNOWLEDGE_PATH.with_suffix(f".md.before_learn_{stamp}"))

    header = (
        f"<!-- Собрано автоматически learn.py, "
        f"{datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}, "
        f"новых реплик: {n_new} -->\n\n"
    )
    KNOWLEDGE_PATH.write_text(header + text + "\n", encoding="utf-8")
    meta_set(conn, "learn_last_message_id", max_id)

    print(f"[learn] OK - обработано реплик: {n_new}, "
          f"выжимка: {len(text)} символов, курсор: {max_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
