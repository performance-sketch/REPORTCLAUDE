#!/usr/bin/env python3
"""
Recalcula o HEATMAP (mês da reserva x mês do voo) a partir dos bookings
CONFIRMED da Rezdy e patcha "const HEATMAP = {...};" em index.html.

Env:  REZDY_API_KEY (opcional — usa o fallback do gerar_dashboard.py se ausente)
Run:  python scripts/update_heatmap.py
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gerar_dashboard as gd

INDEX_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "index.html"))

if os.environ.get("REZDY_API_KEY"):
    gd.REZDY_KEY = os.environ["REZDY_API_KEY"]


def main():
    print("Buscando reservas Rezdy (histórico completo)...")
    reservas = gd.buscar_rezdy_reservas(5000, date_start="2019-01-01")
    print(f"  {len(reservas)} reservas")

    heatmap = defaultdict(lambda: defaultdict(int))
    for b in reservas:
        if b.get("status") != "CONFIRMED":
            continue
        created_ym = gd._utc_to_brt_date(b.get("dateCreated") or "")[:7]
        itens = b.get("items", [])
        if not itens:
            continue
        tour_ym = (itens[0].get("startTimeLocal") or "")[:7]
        if created_ym and tour_ym:
            heatmap[created_ym][tour_ym] += 1

    heatmap_dict = {k: dict(v) for k, v in sorted(heatmap.items())}
    novo_json = json.dumps(heatmap_dict, ensure_ascii=False, separators=(", ", ": "))

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    padrao = r"(const HEATMAP\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        sys.exit("ERRO: HEATMAP não encontrado em index.html")

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(novo_html)
    print(f"Updated HEATMAP in index.html ({len(heatmap_dict)} meses de reserva)")


if __name__ == "__main__":
    main()
