#!/usr/bin/env python3
"""Проверка ответов: объекты только из базы, без заглушек и длинных тире."""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import realty_bot as rb


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None):
        self.sent.append(text)


class FakeCtx:
    def __init__(self):
        self.bot = FakeBot()


def norm_price(s):
    return re.sub(r"\D", "", s or "")


def base_title_key(title):
    """«Parklane (Jomthien)» -> «parklane»: модель опускает суффикс района."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title or "").strip().lower()


# Заглушки ищем только в связке с единицами - голый «?» есть в любом URL.
PLACEHOLDER_RE = re.compile(
    r"\?\s*(м²|m²|спал|bed|THB|бат)|не указано|нет данных|N/A", re.I
)

QUERIES = [
    ("Ищу квартиру до 3 млн бат. Джомтьен, 1 спальня. Покажи варианты.", "ru"),
    ("Show me houses in Bang Sare, budget 8 million baht", "en"),
    ("Есть вилла с бассейном в Наклуа до 5 млн?", "ru"),
]


async def main():
    rb.load_knowledge()
    await rb.load_listings()
    titles = {base_title_key(r["Название"]) for r in rb.LISTINGS if r.get("Название")}
    prices = {norm_price(r.get("Цена, THB")) for r in rb.LISTINGS}
    print(f"в базе {len(rb.LISTINGS)} объектов\n")

    all_ok = True
    for q, _lang in QUERIES:
        print(f"=== {q}")
        reply, meta = await rb.ask_ai([{"role": "user", "content": q}], 555, "t", FakeCtx())
        print(reply)
        print(f"[meta] {meta['model']} | токены {meta['input_tokens']}/"
              f"{meta['output_tokens']} | {meta['latency_ms']} мс | "
              f"объекты: {meta.get('offered_ids') or '-'}")

        low = reply.lower()
        matched = sorted(t for t in titles if t and len(t) > 3 and t in low)

        bad_prices = [
            p.strip() for p in re.findall(r"\d[\d\s ., ]{5,}\d", reply)
            if len(norm_price(p)) >= 6 and norm_price(p) not in prices
        ]
        holes = PLACEHOLDER_RE.findall(reply)
        dashes = [c for c in "—–‒−―" if c in reply]
        md = [m for m in ("**", "##", "- [") if m in reply]

        print(f"  названия из базы: {len(matched)} {matched[:6]}")
        print(f"  цены не из базы:  {bad_prices or 'нет'}")
        print(f"  заглушки:         {holes or 'нет'}")
        print(f"  длинные тире:     {dashes or 'нет'}")
        print(f"  markdown:         {md or 'нет'}")

        if bad_prices or holes or dashes or md:
            all_ok = False
        if not matched and "нет" not in low and "no " not in low:
            print("  !! объектов не предложено и не сказано, что их нет")
            all_ok = False
        print()

    print("=== ИТОГ:", "OK" if all_ok else "ТРЕБУЕТ ВНИМАНИЯ", "===")
    return 0 if all_ok else 1


sys.exit(asyncio.run(main()))
