#!/usr/bin/env python3
"""
analisar_cupons.py — Vertical Rio
Análise completa de voos confirmados via cupom no Rezdy.

Uso:
  python analisar_cupons.py                          # últimos 90 dias
  python analisar_cupons.py --from 2026-05-01        # a partir de uma data
  python analisar_cupons.py --from 2026-05-01 --to 2026-05-31
  python analisar_cupons.py --cupom CARIOQUINHA      # filtrar por cupom específico
  python analisar_cupons.py --json                   # saída em JSON
"""

import argparse
import json
import sys
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict

REZDY_KEY  = "dc7f8d97256e484b8763a983ded2ba22"
REZDY_BASE = "https://api.rezdy.com/v1"


# ─── Busca ────────────────────────────────────────────────────────────────────
def buscar_reservas(limite=3000):
    todas, offset = [], 0
    while offset < limite:
        resp = requests.get(f"{REZDY_BASE}/bookings", params={
            "apiKey": REZDY_KEY, "limit": 100, "offset": offset,
        }, timeout=20)
        resp.raise_for_status()
        lote = resp.json().get("bookings", [])
        if not lote:
            break
        todas.extend(lote)
        sys.stderr.write(f"\r  Buscando... {len(todas)} reservas")
        sys.stderr.flush()
        if len(lote) < 100:
            break
        offset += 100
        time.sleep(0.1)
    sys.stderr.write("\n")
    return todas


# ─── Filtra e agrega ──────────────────────────────────────────────────────────
def filtrar_cupons(reservas, date_from, date_to, cupom_filtro=None):
    voos = []
    for b in reservas:
        coupon = (b.get("coupon") or "").strip().upper()
        if not coupon:
            continue
        if b.get("status") != "CONFIRMED":
            continue
        data = (b.get("dateCreated") or "")[:10]
        if data < date_from or data > date_to:
            continue
        if cupom_filtro and coupon != cupom_filtro.upper():
            continue

        itens   = b.get("items", [])
        produto = itens[0].get("productName", "-") if itens else "-"
        tour_dt = (itens[0].get("startTimeLocal") or "")[:10] if itens else ""
        pax     = sum(
            sum(q.get("value", 0) for q in item.get("quantities", []))
            for item in itens
        ) or sum(i.get("totalQuantity", 1) for i in itens)

        voos.append({
            "numero":  b.get("orderNumber", ""),
            "coupon":  coupon,
            "produto": produto,
            "pax":     pax,
            "valor":   round(float(b.get("totalAmount", 0) or 0), 2),
            "data":    data,
            "tour_dt": tour_dt,
            "nome":    (b.get("customer") or {}).get("name", "-"),
            "email":   (b.get("customer") or {}).get("email", "-"),
        })

    voos.sort(key=lambda x: x["data"], reverse=True)
    return voos


def agregar_por_cupom(voos):
    agr = defaultdict(lambda: {
        "usos": 0, "receita": 0.0, "pax_total": 0,
        "produtos": defaultdict(int), "datas": [],
    })
    for v in voos:
        c = v["coupon"]
        agr[c]["usos"]       += 1
        agr[c]["receita"]    += v["valor"]
        agr[c]["pax_total"]  += v["pax"]
        agr[c]["produtos"][v["produto"]] += 1
        agr[c]["datas"].append(v["data"])

    resultado = []
    for cupom, d in agr.items():
        produto_top = max(d["produtos"], key=d["produtos"].get) if d["produtos"] else "-"
        resultado.append({
            "cupom":       cupom,
            "usos":        d["usos"],
            "receita":     round(d["receita"], 2),
            "ticket_medio":round(d["receita"] / d["usos"], 2) if d["usos"] else 0,
            "pax_total":   d["pax_total"],
            "produto_top": produto_top,
            "primeira_uso":min(d["datas"]),
            "ultimo_uso":  max(d["datas"]),
        })

    return sorted(resultado, key=lambda x: x["usos"], reverse=True)


# ─── Saída formatada ──────────────────────────────────────────────────────────
def fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def imprimir_relatorio(voos, resumo, date_from, date_to, cupom_filtro):
    total_receita = sum(v["valor"] for v in voos)
    total_pax     = sum(v["pax"]   for v in voos)

    print()
    print("=" * 68)
    print("  VERTICAL RIO — ANÁLISE DE CUPONS REZDY")
    print(f"  Periodo: {date_from}  a  {date_to}")
    if cupom_filtro:
        print(f"  Filtro cupom: {cupom_filtro}")
    print("=" * 68)
    print(f"  Total voos confirmados c/ cupom : {len(voos)}")
    print(f"  Cupons distintos                : {len(resumo)}")
    print(f"  Receita total                   : {fmt_brl(total_receita)}")
    print(f"  PAX total                       : {total_pax}")
    print()

    # Resumo por cupom
    print("  RESUMO POR CUPOM")
    print("  " + "-" * 66)
    print(f"  {'CUPOM':<22} {'VOOS':>5} {'RECEITA':>14} {'TICKET':>12} {'PAX':>5}  PRODUTO TOP")
    print("  " + "-" * 66)
    for r in resumo:
        print(f"  {r['cupom']:<22} {r['usos']:>5} {fmt_brl(r['receita']):>14} "
              f"{fmt_brl(r['ticket_medio']):>12} {r['pax_total']:>5}  {r['produto_top'][:22]}")
    print()

    # Detalhe por voo
    print("  DETALHE POR VOO")
    print("  " + "-" * 66)
    print(f"  {'PEDIDO':<12} {'CUPOM':<22} {'DATA':>10} {'VOO':>10} {'VALOR':>12}  CLIENTE")
    print("  " + "-" * 66)
    for v in voos:
        print(f"  {v['numero']:<12} {v['coupon']:<22} {v['data']:>10} "
              f"{(v['tour_dt'] or '—'):>10} {fmt_brl(v['valor']):>12}  {v['nome'][:20]}")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Análise de cupons Rezdy — Vertical Rio")
    parser.add_argument("--from",  dest="date_from", default=None,
                        help="Data início YYYY-MM-DD (padrão: 90 dias atrás)")
    parser.add_argument("--to",    dest="date_to",   default=None,
                        help="Data fim YYYY-MM-DD (padrão: hoje)")
    parser.add_argument("--cupom", dest="cupom",     default=None,
                        help="Filtrar por cupom específico (ex: CARIOQUINHA)")
    parser.add_argument("--json",  action="store_true",
                        help="Saída em JSON em vez de texto formatado")
    parser.add_argument("--limite", type=int, default=3000,
                        help="Máximo de reservas a buscar (padrão: 3000)")
    args = parser.parse_args()

    hoje      = datetime.now().strftime("%Y-%m-%d")
    date_from = args.date_from or (datetime.now() - timedelta(days=89)).strftime("%Y-%m-%d")
    date_to   = args.date_to   or hoje

    if date_from > date_to:
        print("Erro: --from deve ser anterior a --to", file=sys.stderr)
        sys.exit(1)

    sys.stderr.write(f"Buscando reservas ({date_from} a {date_to})...\n")
    reservas = buscar_reservas(limite=args.limite)
    sys.stderr.write(f"{len(reservas)} reservas recuperadas. Filtrando...\n")

    voos   = filtrar_cupons(reservas, date_from, date_to, args.cupom)
    resumo = agregar_por_cupom(voos)

    if args.json:
        print(json.dumps({
            "periodo":  {"from": date_from, "to": date_to},
            "cupom_filtro": args.cupom,
            "total_voos":   len(voos),
            "total_cupons": len(resumo),
            "resumo":       resumo,
            "voos":         voos,
        }, ensure_ascii=False, indent=2))
    else:
        imprimir_relatorio(voos, resumo, date_from, date_to, args.cupom)


if __name__ == "__main__":
    main()
