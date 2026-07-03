#!/usr/bin/env python3
"""
Correção pontual dos dados de março/2026 na aba Rezdy do index.html,
usando exports oficiais da Rezdy (Reports) em vez da API /v1/bookings,
que demonstrou perder a maioria dos pedidos durante a paginação.

Fontes:
  18_order_table  -> pedidos confirmados com voo (fulfilment) em março/2026 (374)
  15_customer_table -> country_code por pedido
  19_order_daily_table -> contagem diária de pedidos criados (order_booked_on)

Uso: python scripts/fix_marco_2026.py
"""
import csv
import json
import re
from collections import defaultdict

ORDER_CSV    = r"C:\Users\info\Downloads\18_order_table_2026-07-03T15_24_17.101359Z.csv"
CUSTOMER_CSV = r"C:\Users\info\Downloads\15_customer_table_2026-07-03T15_24_13.453476Z.csv"
DAILY_CSV    = r"C:\Users\info\Downloads\19_order_daily_table_2026-07-03T15_24_20.85057Z.csv"
INDEX_HTML   = "index.html"


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    orders = load_csv(ORDER_CSV)
    customers = load_csv(CUSTOMER_CSV)
    daily = load_csv(DAILY_CSV)

    cc_by_order = {c["order_number"]: (c["country_code"] or "??").upper() for c in customers}

    # ── Reconstrói bookings de marco (por fulfilment) no schema do dashboard ──
    novos_bookings = []
    for o in orders:
        if o["order_status"].upper() != "CONFIRMED":
            continue
        produto = o["product_name"].split(",")[0].strip() or "-"
        novos_bookings.append({
            "n":  o["order_number"],
            "s":  "CONFIRMED",
            "p":  produto,
            "v":  round(float(o["order_total_amount"] or 0), 2),
            "d":  o["order_created_at"][:10],
            "t":  o["order_fulfilment_at"][:10],
            "f":  (o["order_source"] or "ONLINE").upper(),
            "cc": cc_by_order.get(o["order_number"], "??"),
            "px": int(float(o["num_participant"] or 1)),
        })
    print(f"Bookings reconstruidos (fulfilment em marco, confirmados): {len(novos_bookings)}")

    # ── Contagem diaria por data de criacao (order_booked_on) ──────────────
    daily_marco = {}
    for d in daily:
        data = d["order_booked_on"][:10]
        if data[:7] != "2026-03":
            continue
        daily_marco[data] = {
            "confirmadas": int(d["number_of_orders"]),
            "receita": round(float(d["Order_Value"]), 2),
        }
    print(f"Dias de marco com dados oficiais (criacao): {len(daily_marco)}")

    # ── Le index.html ───────────────────────────────────────────────────────
    html = open(INDEX_HTML, encoding="utf-8").read()

    def extract(nome, abre, fecha):
        padrao = "const " + nome + r"\s*=\s*(" + re.escape(abre) + ".*?" + re.escape(fecha) + r")\s*;\n"
        m = re.search(padrao, html, re.S)
        return json.loads(m.group(1)), m.span(1)

    bookings, bk_span = extract("BOOKINGS", "[", "]")
    rezdy, rz_span   = extract("REZDY_DATA", "{", "}")
    heatmap, hm_span = extract("HEATMAP", "{", "}")

    # ── 1) BOOKINGS: remove entradas antigas com voo em marco/2026, adiciona as corretas
    antes = len(bookings)
    bookings = [b for b in bookings if not b["t"].startswith("2026-03")]
    removidos = antes - len(bookings)
    bookings.extend(novos_bookings)
    bookings.sort(key=lambda b: b["d"], reverse=True)
    print(f"BOOKINGS: removidos {removidos} (dados antigos incompletos), adicionados {len(novos_bookings)}")

    # ── 2) REZDY_DATA.por_dia: corrige dias de marco (por data de criacao) ──
    por_dia = {d["data"]: d for d in rezdy["por_dia"]}
    delta_confirmadas = 0
    delta_receita = 0.0
    for data, info in daily_marco.items():
        antigo = por_dia.get(data, {"data": data, "confirmadas": 0, "abandonadas": 0, "outras": 0, "receita": 0.0})
        delta_confirmadas += info["confirmadas"] - antigo["confirmadas"]
        delta_receita     += info["receita"] - antigo["receita"]
        antigo["confirmadas"] = info["confirmadas"]
        antigo["receita"] = info["receita"]
        por_dia[data] = antigo
    rezdy["por_dia"] = sorted(por_dia.values(), key=lambda x: x["data"])

    # ── 3) Totais agregados: aplica o delta apurado ─────────────────────────
    rezdy["confirmadas"] = rezdy["confirmadas"] + delta_confirmadas
    rezdy["total"]       = rezdy["total"] + delta_confirmadas
    rezdy["receita"]     = round(rezdy["receita"] + delta_receita, 2)
    rezdy["ticket_medio"] = round(rezdy["receita"] / rezdy["confirmadas"], 2) if rezdy["confirmadas"] else 0
    rezdy["taxa_conv"]    = round(rezdy["confirmadas"] / rezdy["total"] * 100, 1) if rezdy["total"] else 0

    # fulfilments: mesma logica (marco inteiro ja esta no passado -> conta como voo realizado)
    # removidos já eram só os confirmados com voo em marco (base antiga); todos os novos contam
    old_fulfil_marco = removidos
    new_fulfil_marco = len(novos_bookings)
    rezdy["fulfilments"] = rezdy["fulfilments"] + (new_fulfil_marco - old_fulfil_marco)
    print(f"Delta bookings/receita (criacao, marco): +{delta_confirmadas} confirmadas, +R${delta_receita:,.2f}")
    print(f"Delta fulfilments (voo, marco): {old_fulfil_marco} -> {new_fulfil_marco}")

    # ── 4) HEATMAP: zera a coluna 2026-03 (tour month) e recalcula com dados oficiais
    for created_ym in list(heatmap.keys()):
        if "2026-03" in heatmap[created_ym]:
            del heatmap[created_ym]["2026-03"]
    contagem = defaultdict(int)
    for b in novos_bookings:
        created_ym = b["d"][:7]
        contagem[created_ym] += 1
    for created_ym, qtd in contagem.items():
        heatmap.setdefault(created_ym, {})["2026-03"] = qtd
    heatmap = dict(sorted(heatmap.items()))

    # ── Grava de volta no index.html ─────────────────────────────────────────
    def replace_span(html, span, novo_json):
        return html[:span[0]] + novo_json + html[span[1]:]

    # Recalcula spans na ordem inversa (para nao invalidar offsets já usados)
    partes = [
        (bk_span, json.dumps(bookings, ensure_ascii=False)),
        (rz_span, json.dumps(rezdy, ensure_ascii=False)),
        (hm_span, json.dumps(heatmap, ensure_ascii=False)),
    ]
    partes.sort(key=lambda x: x[0][0], reverse=True)
    for span, novo_json in partes:
        html = replace_span(html, span, novo_json)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html atualizado com sucesso.")


if __name__ == "__main__":
    main()
