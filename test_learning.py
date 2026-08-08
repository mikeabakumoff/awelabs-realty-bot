#!/usr/bin/env python3
"""Прогон цикла обучения: диалоги -> корпус -> learn.py -> knowledge.md."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import realty_bot as rb


class B:
    async def send_message(self, **k):
        pass


class C:
    bot = B()


DIALOGS = {
    901: ["Здравствуйте! Ищу студию в Джомтьене до 2 млн",
          "А налоги и содержание какие? И можно сдавать в аренду?",
          "Спасибо, меня зовут Игорь, телефон +66 89 111 2233"],
    902: ["Hi! Looking for a villa with a pool in Naklua, budget 5 million baht",
          "Nothing in Naklua? What about Pratumnak?"],
    903: ["Нужен дом на первой линии моря до 10 млн",
          "Дороговато. А в рассрочку от застройщика можно?"],
}


async def main():
    rb.load_knowledge()
    await rb.load_listings()
    print(f"объектов: {len(rb.LISTINGS)} | knowledge до прогона: {len(rb.KNOWLEDGE)} симв.\n")

    for uid, msgs in DIALOGS.items():
        print(f"--- диалог {uid} ---")
        for m in msgs:
            rb.save_message(uid, "user", m)
            hist = rb.load_history(uid)
            reply, meta = await rb.ask_ai(hist, uid, f"user{uid}", C())
            rb.save_message(uid, "assistant", reply, **meta)
            print(f"К: {m}\nА: {reply[:160]}...")
            print(f"   [meta] токены {meta['input_tokens']}/{meta['output_tokens']}, "
                  f"{meta['latency_ms']} мс, объекты: {meta.get('offered_ids') or '-'}, "
                  f"заявка: {meta['led_to_lead']}")
        print()

    rows = rb.conn.execute(
        "SELECT COUNT(*), SUM(led_to_lead), SUM(input_tokens), SUM(output_tokens) "
        "FROM messages"
    ).fetchone()
    print(f"[корпус] реплик: {rows[0]}, заявок: {rows[1]}, "
          f"токенов вход/выход: {rows[2]}/{rows[3]}")
    langs = rb.conn.execute(
        "SELECT lang, COUNT(*) FROM messages GROUP BY lang"
    ).fetchall()
    print(f"[корпус] языки: {dict(langs)}")


asyncio.run(main())
