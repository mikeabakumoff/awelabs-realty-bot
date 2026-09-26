#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import realty_bot as rb


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text))
        print(f"\n>>> УВЕДОМЛЕНИЕ в чат {chat_id}:\n{text}")


class FakeCtx:
    def __init__(self):
        self.bot = FakeBot()


async def main():
    print("=== 1. ЗАГРУЗКА БАЗЫ ===")
    await rb.load_listings()
    print(f"объектов загружено: {len(rb.LISTINGS)} | обновлено: {rb.LISTINGS_UPDATED}")
    if not rb.LISTINGS:
        print("ПРОВАЛ: база пуста")
        return 1
    print("первый объект:", rb.LISTINGS[0])
    print("колонки:", list(rb.LISTINGS[0].keys()))

    sp = rb.build_system_prompt()
    print(f"системный промпт: {len(sp)} символов")

    ctx = FakeCtx()
    uid = 999000111
    history = []

    print("\n=== 2. ЗАПРОС «ищу квартиру до 3 млн бат» ===")
    history.append({"role": "user", "content": "Привет! Ищу квартиру до 3 млн бат"})
    reply, _ = await rb.ask_ai(history, uid, "tester", ctx)
    print(reply)
    history.append({"role": "assistant", "content": reply})


    titles = [r["Название"] for r in rb.LISTINGS]
    hits = [t for t in titles if t and t.lower()[:18] in reply.lower()]
    print(f"\n[проверка] названий из базы найдено в ответе: {len(hits)} -> {hits[:5]}")

    print("\n=== 3. АНГЛИЙСКИЙ ===")
    en, _ = await rb.ask_ai(
        [{"role": "user", "content": "Do you have a house in Jomtien?"}],
        uid, "tester", ctx,
    )
    print(en)

    print("\n=== 4. ЗАЯВКА (имя + телефон) ===")
    history.append({"role": "user",
                    "content": "Отлично, меня зовут Михаил, телефон +66 81 234 5678"})
    reply2, _ = await rb.ask_ai(history, uid, "tester", ctx)
    print(reply2)

    leads = rb.conn.execute(
        "SELECT id, name, phone, summary FROM leads ORDER BY id DESC LIMIT 3"
    ).fetchall()
    print(f"\n[проверка] заявок в БД: {leads}")
    print(f"[проверка] уведомлений отправлено: {len(ctx.bot.sent)}")

    ok = bool(leads) and len(hits) > 0
    print("\n=== ИТОГ:", "OK" if ok else "ЕСТЬ ПРОБЛЕМЫ", "===")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
