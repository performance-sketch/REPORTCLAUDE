#!/usr/bin/env python3
"""
gerar_dashboard.py — Vertical Rio Marketing Dashboard
Busca dados ao vivo de Meta Ads e Rezdy e gera index.html.
Execute: python gerar_dashboard.py
"""

import json
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ─── Credenciais ──────────────────────────────────────────────────────────────
META_TOKEN   = "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dnZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11KH8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
META_ACCOUNT = "act_2613909812239242"
META_BASE    = "https://graph.facebook.com/v19.0"
REZDY_KEY    = "dc7f8d97256e484b8763a983ded2ba22"
REZDY_BASE   = "https://api.rezdy.com/v1"
ARQUIVO_HTML = "index.html"

# ─── Meta Ads ─────────────────────────────────────────────────────────────────
def meta_get(endpoint, params=None):
    p = {"access_token": META_TOKEN, **(params or {})}
    r = requests.get(f"{META_BASE}/{endpoint}", params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def _paginar(resp):
    dados = list(resp.get("data", []))
    while resp.get("paging", {}).get("next"):
        resp = requests.get(resp["paging"]["next"], timeout=20).json()
        dados.extend(resp.get("data", []))
    return dados


def _extrair_acoes(actions):
    """Separa todas as action types de mensagens para permitir análise granular."""
    out = {
        "conexoes":        0,   # total_messaging_connection
        "first_reply":     0,   # messaging_first_reply
        "conversas":       0,   # conversation_started_7d  ← mensagens iniciadas
        "bloqueios":       0,   # messaging_block
        "adicao_carrinho": 0,   # add_to_cart / omni_add_to_cart
        "compras":         0,
        "valor_compras":   0.0,
    }
    for a in (actions or []):
        at = a.get("action_type", "")
        v  = float(a.get("value", 0) or 0)
        if "total_messaging_connection" in at:
            out["conexoes"] += int(v)
        elif "messaging_first_reply" in at:
            out["first_reply"] += int(v)
        elif "conversation_started" in at:
            out["conversas"] += int(v)
        elif "messaging_block" in at:
            out["bloqueios"] += int(v)
        elif at == "omni_add_to_cart":
            out["adicao_carrinho"] += int(v)
        elif at in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"):
            out["compras"]       += int(v)
            out["valor_compras"] += v
    return out


def buscar_meta_periodo(preset):
    fields = "spend,impressions,clicks,reach,cpc,ctr,cpm,actions"
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level": "account", "fields": fields, "date_preset": preset, "limit": 1,
    })
    row  = (resp.get("data") or [{}])[0]
    spend  = float(row.get("spend", 0) or 0)
    impr   = int(row.get("impressions", 0) or 0)
    clicks = int(row.get("clicks", 0) or 0)
    acoes  = _extrair_acoes(row.get("actions"))
    return {
        "gasto":       round(spend, 2),
        "impressoes":  impr,
        "cliques":     clicks,
        "alcance":     int(row.get("reach", 0) or 0),
        "ctr":         round(float(row.get("ctr", 0) or 0), 2),
        "cpc":         round(float(row.get("cpc", 0) or 0), 2) if row.get("cpc") else round(spend/clicks, 2) if clicks else 0,
        "cpm":         round(float(row.get("cpm", 0) or 0), 2),
        "conexoes":    acoes["conexoes"],
        "first_reply": acoes["first_reply"],
        "conversas":   acoes["conversas"],
        "bloqueios":   acoes["bloqueios"],
        "compras_meta":acoes["compras"],
        "roas":        round(acoes["valor_compras"] / spend, 2) if spend else 0,
    }


def buscar_meta_campanhas(preset="last_30d"):
    fields = "campaign_name,campaign_id,spend,impressions,clicks,ctr,cpc,reach,actions"
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level": "campaign", "fields": fields, "date_preset": preset, "limit": 100,
    })
    dados = _paginar(resp)
    resultado = []
    for c in dados:
        spend = float(c.get("spend", 0) or 0)
        acoes = _extrair_acoes(c.get("actions"))
        resultado.append({
            "nome":        c.get("campaign_name", "?"),
            "id":          c.get("campaign_id", ""),
            "gasto":       round(spend, 2),
            "impressoes":  int(c.get("impressions", 0) or 0),
            "cliques":     int(c.get("clicks", 0) or 0),
            "ctr":         round(float(c.get("ctr", 0) or 0), 2),
            "cpc":         round(float(c.get("cpc", 0) or 0), 2) if c.get("cpc") else 0,
            "alcance":     int(c.get("reach", 0) or 0),
            "conexoes":              acoes["conexoes"],
            "first_reply":           acoes["first_reply"],
            "conversas":             acoes["conversas"],
            "adicao_carrinho":       acoes["adicao_carrinho"],
            "custo_por_msg":         round(spend / acoes["conversas"],       2) if acoes["conversas"]       else 0,
            "custo_por_carrinho":    round(spend / acoes["adicao_carrinho"], 2) if acoes["adicao_carrinho"] else 0,
        })
    resultado.sort(key=lambda x: x["gasto"], reverse=True)
    return resultado


def buscar_meta_criativos(preset="last_30d"):
    fields = "ad_id,ad_name,campaign_name,campaign_id,spend,impressions,clicks,ctr,cpc,actions"
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level": "ad", "fields": fields, "date_preset": preset, "limit": 500,
    })
    dados = _paginar(resp)
    resultado = []
    for a in dados:
        spend = float(a.get("spend", 0) or 0)
        if spend < 1.0:
            continue
        acoes  = _extrair_acoes(a.get("actions"))
        cliques = int(a.get("clicks", 0) or 0)
        resultado.append({
            "id":    a.get("ad_id", ""),
            "nome":  a.get("ad_name", "?"),
            "camp":  a.get("campaign_name", "?"),
            "gasto": round(spend, 2),
            "impr":  int(a.get("impressions", 0) or 0),
            "click": cliques,
            "ctr":   round(float(a.get("ctr", 0) or 0), 2),
            "cpc":   round(float(a.get("cpc", 0) or 0), 2) if a.get("cpc") else (round(spend / cliques, 2) if cliques else 0),
            "msg":   acoes["conversas"],
            "cart":  acoes["adicao_carrinho"],
        })
    resultado.sort(key=lambda x: x["gasto"], reverse=True)
    return resultado


def buscar_meta_diario(dias=90):
    hoje   = datetime.now()
    inicio = hoje - timedelta(days=dias - 1)
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level": "account",
        "fields": "spend,impressions,clicks,actions",
        "time_range": json.dumps({
            "since": inicio.strftime("%Y-%m-%d"),
            "until": hoje.strftime("%Y-%m-%d"),
        }),
        "time_increment": 1,
        "limit": 200,
    })
    dados = _paginar(resp)
    por_dia = {d.get("date_start", ""): d for d in dados}
    resultado = []
    for i in range(dias):
        data = (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
        d    = por_dia.get(data, {})
        spend = float(d.get("spend", 0) or 0)
        acoes = _extrair_acoes(d.get("actions"))
        resultado.append({
            "data":       data,
            "gasto":      round(spend, 2),
            "impressoes": int(d.get("impressions", 0) or 0),
            "cliques":    int(d.get("clicks", 0) or 0),
            "conexoes":   acoes["conexoes"],
            "conversas":  acoes["conversas"],
        })
    return resultado


def buscar_meta_diario_campanhas(dias=90):
    hoje   = datetime.now()
    inicio = hoje - timedelta(days=dias - 1)
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level":    "campaign",
        "fields":   "campaign_name,campaign_id,spend,impressions,clicks,actions",
        "time_range": json.dumps({
            "since": inicio.strftime("%Y-%m-%d"),
            "until": hoje.strftime("%Y-%m-%d"),
        }),
        "time_increment": 1,
        "limit": 500,
    })
    dados = _paginar(resp)
    camps = {}
    for d in dados:
        cid   = d.get("campaign_id", "")
        cname = d.get("campaign_name", "?")
        spend = float(d.get("spend", 0) or 0)
        if not spend:
            continue
        if cid not in camps:
            camps[cid] = {"id": cid, "nome": cname, "daily": {}}
        acoes = _extrair_acoes(d.get("actions"))
        camps[cid]["daily"][d.get("date_start", "")] = {
            "g": round(spend, 2),
            "i": int(d.get("impressions", 0) or 0),
            "c": int(d.get("clicks", 0) or 0),
            "m": acoes["conversas"],
            "a": acoes["adicao_carrinho"],
        }
    return list(camps.values())


# ─── Rezdy ────────────────────────────────────────────────────────────────────
def buscar_rezdy_reservas(limite_total=800):
    todas, offset = [], 0
    while offset < limite_total:
        resp = requests.get(f"{REZDY_BASE}/bookings", params={
            "apiKey": REZDY_KEY, "limit": 100, "offset": offset,
        }, timeout=20)
        resp.raise_for_status()
        lote = resp.json().get("bookings", [])
        if not lote:
            break
        todas.extend(lote)
        if len(lote) < 100:
            break
        offset += 100
        time.sleep(0.1)
    return todas


def processar_rezdy(reservas, dias=90):
    hoje      = datetime.now()
    hoje_str  = hoje.strftime("%Y-%m-%d")
    corte     = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
    recentes  = [b for b in reservas if (b.get("dateCreated") or "")[:10] >= corte]

    por_dia     = defaultdict(lambda: {"confirmadas": 0, "abandonadas": 0, "outras": 0, "receita": 0.0})
    por_produto = defaultdict(lambda: {"ordens": 0, "confirmadas": 0, "receita": 0.0})
    por_status  = defaultdict(int)
    por_fonte   = defaultdict(lambda: {"ordens": 0, "receita": 0.0})

    for b in recentes:
        data    = (b.get("dateCreated") or "")[:10]
        status  = b.get("status", "?")
        valor   = float(b.get("totalAmount", 0) or 0)
        fonte   = (b.get("source") or "ONLINE").upper()
        itens   = b.get("items", [])
        produto = itens[0].get("productName", "Desconhecido") if itens else "Desconhecido"

        por_status[status] += 1
        por_fonte[fonte]["ordens"]  += 1
        por_fonte[fonte]["receita"] += valor
        por_produto[produto]["ordens"]  += 1
        por_produto[produto]["receita"] += valor

        if status == "CONFIRMED":
            por_dia[data]["confirmadas"] += 1
            por_dia[data]["receita"]     += valor
            por_produto[produto]["confirmadas"] += 1
        elif status == "ABANDONED_CART":
            por_dia[data]["abandonadas"] += 1
        else:
            por_dia[data]["outras"] += 1

    todos_dias = []
    for i in range(dias):
        d = (hoje - timedelta(days=dias - 1 - i)).strftime("%Y-%m-%d")
        v = por_dia[d]
        todos_dias.append({
            "data":        d,
            "confirmadas": v["confirmadas"],
            "abandonadas": v["abandonadas"],
            "outras":      v["outras"],
            "receita":     round(v["receita"], 2),
        })

    confirmadas_total = sum(b["confirmadas"] for b in todos_dias)
    abandonadas_total = sum(b["abandonadas"] for b in todos_dias)
    receita_total     = round(sum(b["receita"] for b in todos_dias), 2)
    ticket_medio      = round(receita_total / confirmadas_total, 2) if confirmadas_total else 0
    taxa_conv         = round(confirmadas_total / len(recentes) * 100, 1) if recentes else 0

    produtos_lista = sorted(
        [{"produto": k, **{kk: round(v[kk], 2) if kk == "receita" else v[kk] for kk in v}}
         for k, v in por_produto.items()],
        key=lambda x: x["receita"], reverse=True,
    )

    # Voos realizados: confirmados com tour_date < hoje (no período 90d)
    fulfilments = sum(
        1 for b in recentes
        if b.get("status") == "CONFIRMED"
        and b.get("items")
        and (b["items"][0].get("startTimeLocal") or "")[:10] < hoje_str
    )

    # Heatmap: mês da criação × mês do voo (todos os reservas buscados)
    heatmap = defaultdict(lambda: defaultdict(int))
    for b in reservas:
        if b.get("status") != "CONFIRMED":
            continue
        created_ym = (b.get("dateCreated") or "")[:7]
        itens = b.get("items", [])
        if not itens:
            continue
        tour_ym = (itens[0].get("startTimeLocal") or "")[:7]
        if created_ym and tour_ym:
            heatmap[created_ym][tour_ym] += 1
    heatmap_dict = {k: dict(v) for k, v in sorted(heatmap.items())}

    # Todos os bookings do período (compacto para JS) — inclui tour date e país
    todos_bookings = []
    for b in sorted(recentes, key=lambda x: x.get("dateCreated", ""), reverse=True):
        itens   = b.get("items", [])
        produto = itens[0].get("productName", "-") if itens else "-"
        tour_dt = (itens[0].get("startTimeLocal") or "")[:10] if itens else ""
        pax     = sum(i.get("totalQuantity", 1) for i in itens) if itens else 1
        cc      = (b.get("customer", {}).get("countryCode") or "??").upper()
        todos_bookings.append({
            "n":  b.get("orderNumber", ""),
            "s":  b.get("status", ""),
            "p":  produto,
            "v":  round(float(b.get("totalAmount", 0) or 0), 2),
            "d":  (b.get("dateCreated") or "")[:10],
            "t":  tour_dt,
            "f":  (b.get("source") or "ONLINE").upper(),
            "cc": cc,
            "px": pax,
        })

    # ── Voos confirmados com cupom ─────────────────────────────────────────────
    voos_cupom   = []
    cupom_resumo = defaultdict(lambda: {"usos": 0, "receita": 0.0, "produtos": defaultdict(int)})
    for b in sorted(recentes, key=lambda x: x.get("dateCreated", ""), reverse=True):
        coupon = (b.get("coupon") or "").strip().upper()
        if not coupon or b.get("status") != "CONFIRMED":
            continue
        itens   = b.get("items", [])
        produto = itens[0].get("productName", "-") if itens else "-"
        tour_dt = (itens[0].get("startTimeLocal") or "")[:10] if itens else ""
        pax     = sum(
            sum(q.get("value", 0) for q in item.get("quantities", []))
            for item in itens
        ) or sum(i.get("totalQuantity", 1) for i in itens)
        valor = float(b.get("totalAmount", 0) or 0)
        voos_cupom.append({
            "numero":  b.get("orderNumber", ""),
            "coupon":  coupon,
            "produto": produto,
            "pax":     pax,
            "valor":   round(valor, 2),
            "data":    (b.get("dateCreated") or "")[:10],
            "tour_dt": tour_dt,
            "nome":    (b.get("customer") or {}).get("name", "-"),
        })
        cupom_resumo[coupon]["usos"]    += 1
        cupom_resumo[coupon]["receita"] += valor
        cupom_resumo[coupon]["produtos"][produto] += 1

    cupom_resumo_lista = sorted(
        [{"cupom": k, "usos": v["usos"], "receita": round(v["receita"], 2),
          "ticket": round(v["receita"] / v["usos"], 2) if v["usos"] else 0,
          "produto_top": max(v["produtos"], key=v["produtos"].get) if v["produtos"] else "-"}
         for k, v in cupom_resumo.items()],
        key=lambda x: x["usos"], reverse=True,
    )

    return {
        "total":          len(recentes),
        "confirmadas":    confirmadas_total,
        "abandonadas":    abandonadas_total,
        "outras":         len(recentes) - confirmadas_total - abandonadas_total,
        "receita":        receita_total,
        "ticket_medio":   ticket_medio,
        "taxa_conv":      taxa_conv,
        "fulfilments":    fulfilments,
        "por_dia":        todos_dias,
        "por_status":     dict(por_status),
        "por_produto":    produtos_lista,
        "por_fonte":      {k: {"ordens": v["ordens"], "receita": round(v["receita"], 2)}
                           for k, v in por_fonte.items()},
        "todos_bookings": todos_bookings,
        "heatmap":        heatmap_dict,
        "voos_cupom":     voos_cupom,
        "cupom_resumo":   cupom_resumo_lista,
    }


# ─── HTML ─────────────────────────────────────────────────────────────────────
def gerar_html(meta, rezdy_dados, camps_diario, criativos, atualizado_em):
    d30 = meta["d30"]
    rz  = rezdy_dados

    # Remove campos pesados de rezdy_json (embutidos separado)
    _excluir = ("todos_bookings", "heatmap", "voos_cupom", "cupom_resumo")
    rz_slim = {k: v for k, v in rz.items() if k not in _excluir}
    meta_json        = json.dumps(meta,                   ensure_ascii=False)
    rezdy_json       = json.dumps(rz_slim,                ensure_ascii=False)
    camps_diario_json= json.dumps(camps_diario,           ensure_ascii=False)
    bookings_json    = json.dumps(rz["todos_bookings"],   ensure_ascii=False)
    heatmap_json     = json.dumps(rz["heatmap"],          ensure_ascii=False)
    criativos_json   = json.dumps(criativos,              ensure_ascii=False)
    voos_cupom_json  = json.dumps(rz["voos_cupom"],       ensure_ascii=False)
    cupom_resumo_json= json.dumps(rz["cupom_resumo"],     ensure_ascii=False)

    hoje_str   = datetime.now().strftime("%Y-%m-%d")
    d30_str    = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
    d90_str    = (datetime.now() - timedelta(days=89)).strftime("%Y-%m-%d")

    def fmt_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    def fmt_n(v):   return f"{int(v):,}".replace(",", ".")
    def fmt_pct(v): return f"{v:.2f}%"

    # Cupons agora são 100 % dinâmicos via JS — sem rows pré-geradas no Python


    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vertical Rio — Marketing Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/themes/dark.css">
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/pt.js"></script>
<style>
  :root {{
    --bg:#0f172a; --surface:#1e293b; --surface2:#263248;
    --border:#334155; --text:#f1f5f9; --sub:#94a3b8;
    --indigo:#6366f1; --green:#22c55e; --amber:#f59e0b;
    --red:#ef4444; --cyan:#06b6d4;
  }}
  body {{ background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; }}
  .kpi-val {{ font-size:1.75rem; font-weight:700; line-height:1.1; }}
  .kpi-label {{ font-size:0.72rem; color:var(--sub); text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }}
  .kpi-delta {{ font-size:0.75rem; margin-top:4px; color:var(--sub); }}
  .tab-btn {{ padding:8px 18px; border-radius:8px; font-size:.875rem; font-weight:500; cursor:pointer; border:none; transition:all .15s; }}
  .tab-btn.active {{ background:var(--indigo); color:#fff; }}
  .tab-btn:not(.active) {{ background:var(--surface2); color:var(--sub); }}
  .tab-btn:hover:not(.active) {{ background:var(--border); color:var(--text); }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:99px; font-size:.7rem; font-weight:600; }}
  .badge-green {{ background:rgba(34,197,94,.15); color:#22c55e; }}
  .badge-red   {{ background:rgba(239,68,68,.15);  color:#ef4444; }}
  .badge-amber {{ background:rgba(245,158,11,.15); color:#f59e0b; }}
  .badge-gray  {{ background:rgba(148,163,184,.1); color:#94a3b8; }}
  .badge-blue  {{ background:rgba(99,102,241,.15); color:#818cf8; }}
  table {{ width:100%; border-collapse:collapse; font-size:.82rem; }}
  th {{ color:var(--sub); font-weight:500; text-align:left; padding:8px 12px; border-bottom:1px solid var(--border); font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; }}
  td {{ padding:9px 12px; border-bottom:1px solid rgba(51,65,85,.5); }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:rgba(99,102,241,.04); }}
  /* Flatpickr custom */
  .flatpickr-calendar {{ background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:12px !important; box-shadow:0 20px 40px rgba(0,0,0,.5) !important; }}
  .flatpickr-day.selected, .flatpickr-day.startRange, .flatpickr-day.endRange {{ background:var(--indigo) !important; border-color:var(--indigo) !important; }}
  .flatpickr-day.inRange {{ background:rgba(99,102,241,.2) !important; border-color:transparent !important; }}
  .flatpickr-day:hover {{ background:var(--surface2) !important; }}
  .flatpickr-months {{ border-bottom:1px solid var(--border); }}
  .date-range-wrap {{ position:relative; display:flex; align-items:center; gap:8px; background:var(--surface2); border:1px solid var(--border); border-radius:10px; padding:8px 14px; cursor:pointer; transition:border-color .15s; min-width:280px; }}
  .date-range-wrap:hover {{ border-color:var(--indigo); }}
  .date-range-wrap input {{ background:transparent; border:none; outline:none; color:var(--text); font-size:.875rem; width:100%; cursor:pointer; }}
  ::-webkit-scrollbar {{ width:6px; height:6px; }}
  ::-webkit-scrollbar-track {{ background:var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:3px; }}
</style>
</head>
<body>

<!-- HEADER -->
<header class="border-b" style="border-color:var(--border);background:var(--surface)">
  <div class="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between flex-wrap gap-3">
    <div class="flex items-center gap-3">
      <div style="width:36px;height:36px;background:var(--indigo);border-radius:8px;display:flex;align-items:center;justify-content:center;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      </div>
      <div>
        <div style="font-weight:700;font-size:1rem;line-height:1.1">Vertical Rio</div>
        <div style="font-size:.7rem;color:var(--sub)">Marketing Dashboard</div>
      </div>
    </div>
    <div style="font-size:.75rem;color:var(--sub)">
      <span style="color:var(--green)">●</span> Gerado em <strong style="color:var(--text)">{atualizado_em}</strong>
    </div>
  </div>
</header>

<!-- NAV + DATE PICKER -->
<div class="max-w-screen-xl mx-auto px-6 pt-5 pb-3">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex gap-2 flex-wrap">
      <button class="tab-btn active" onclick="switchTab('visao',this)">Visão Geral</button>
      <button class="tab-btn" onclick="switchTab('meta',this)">Meta Ads</button>
      <button class="tab-btn" onclick="switchTab('rezdy',this)">Rezdy Bookings</button>
    </div>
    <!-- Date range picker global -->
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
      <div class="date-range-wrap">
        <input type="text" id="date-range" placeholder="Selecione o período" readonly>
      </div>
      <div id="range-label" style="font-size:.78rem;color:var(--sub);white-space:nowrap"></div>
    </div>
  </div>
</div>

<main class="max-w-screen-xl mx-auto px-6 pb-12">

<!-- ═══════════════════════════ VISÃO GERAL ═══════════════════════════════ -->
<div id="tab-visao" class="tab-content pt-3">

  <div class="mb-2 mt-1" style="font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em">Meta Ads</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" id="vg-meta-kpis">
    <div class="card"><div class="kpi-label">Gasto</div><div class="kpi-val" id="vg-gasto" style="color:var(--indigo)">{fmt_brl(d30["gasto"])}</div></div>
    <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="vg-impr">{fmt_n(d30["impressoes"])}</div></div>
    <div class="card"><div class="kpi-label">CTR</div><div class="kpi-val" id="vg-ctr" style="color:var(--cyan)">{fmt_pct(d30["ctr"])}</div></div>
    <div class="card"><div class="kpi-label">CPC Médio</div><div class="kpi-val" id="vg-cpc">{fmt_brl(d30["cpc"])}</div></div>
  </div>

  <div class="mb-2" style="font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em">Rezdy</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
    <div class="card"><div class="kpi-label">Receita Confirmada</div><div class="kpi-val" id="vg-receita" style="color:var(--green)">{fmt_brl(rz["receita"])}</div></div>
    <div class="card"><div class="kpi-label">Confirmadas</div><div class="kpi-val" id="vg-conf">{rz["confirmadas"]}</div><div class="kpi-delta" id="vg-conf-sub">{rz["total"]} total ({fmt_pct(rz["taxa_conv"])} conv.)</div></div>
    <div class="card"><div class="kpi-label">Ticket Médio</div><div class="kpi-val" id="vg-ticket">{fmt_brl(rz["ticket_medio"])}</div></div>
    <div class="card"><div class="kpi-label">Abandonadas</div><div class="kpi-val" id="vg-aband" style="color:var(--red)">{rz["abandonadas"]}</div><div class="kpi-delta" id="vg-aband-sub">de {rz["total"]} reservas</div></div>
  </div>

  <!-- Charts row 1 -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Gasto & Cliques Diários</div><canvas id="chartMetaDiario" height="200"></canvas></div>
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Reservas por Dia</div><canvas id="chartRezdyDiario" height="200"></canvas></div>
  </div>

  <!-- Funnel -->
  <div class="card mb-4">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:20px">Funil: Meta Ads → Rezdy</div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3" id="funnel-grid">
      <div style="text-align:center">
        <div class="kpi-val" id="fn-impr" style="color:var(--indigo)">{fmt_n(d30["impressoes"])}</div>
        <div style="font-size:.75rem;color:var(--sub);margin-top:2px">Impressões</div>
        <div style="width:100%;height:4px;background:var(--indigo);border-radius:2px;margin-top:8px;opacity:.6"></div>
      </div>
      <div style="text-align:center">
        <div class="kpi-val" id="fn-click" style="color:var(--cyan)">{fmt_n(d30["cliques"])}</div>
        <div style="font-size:.75rem;color:var(--sub);margin-top:2px">Cliques</div>
        <div id="fn-ctr-lbl" style="font-size:.7rem;color:var(--cyan);margin-top:2px">{fmt_pct(d30["ctr"])} CTR</div>
        <div style="width:100%;height:4px;background:var(--cyan);border-radius:2px;margin-top:6px;opacity:.6"></div>
      </div>
      <div style="text-align:center">
        <div class="kpi-val" id="fn-total" style="color:var(--amber)">{rz["total"]}</div>
        <div style="font-size:.75rem;color:var(--sub);margin-top:2px">Reservas Geradas</div>
        <div style="width:100%;height:4px;background:var(--amber);border-radius:2px;margin-top:6px;opacity:.6"></div>
      </div>
      <div style="text-align:center">
        <div class="kpi-val" id="fn-conf" style="color:var(--green)">{rz["confirmadas"]}</div>
        <div style="font-size:.75rem;color:var(--sub);margin-top:2px">Confirmadas</div>
        <div id="fn-taxa-lbl" style="font-size:.7rem;color:var(--green);margin-top:2px">{fmt_pct(rz["taxa_conv"])} taxa</div>
        <div style="width:100%;height:4px;background:var(--green);border-radius:2px;margin-top:6px;opacity:.6"></div>
      </div>
    </div>
  </div>

  <!-- Charts row 2 -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Receita por Produto (período)</div><canvas id="chartProdutos" height="220"></canvas></div>
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Gasto por Campanha (30d)</div><canvas id="chartCampanhas" height="220"></canvas></div>
  </div>

</div><!-- /tab-visao -->


<!-- ═══════════════════════════ META ADS ══════════════════════════════════ -->
<div id="tab-meta" class="tab-content pt-3" style="display:none">

  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" id="meta-kpis-cards">
    <div class="card"><div class="kpi-label">Gasto</div><div class="kpi-val" id="mk-gasto" style="color:var(--indigo)">{fmt_brl(d30["gasto"])}</div></div>
    <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="mk-impr">{fmt_n(d30["impressoes"])}</div></div>
    <div class="card"><div class="kpi-label">Cliques</div><div class="kpi-val" id="mk-click">{fmt_n(d30["cliques"])}</div></div>
    <div class="card"><div class="kpi-label">CTR</div><div class="kpi-val" id="mk-ctr" style="color:var(--cyan)">{fmt_pct(d30["ctr"])}</div></div>
    <div class="card"><div class="kpi-label">CPC</div><div class="kpi-val" id="mk-cpc">{fmt_brl(d30["cpc"])}</div></div>
    <div class="card"><div class="kpi-label">CPM</div><div class="kpi-val" id="mk-cpm">{fmt_brl(d30["cpm"])}</div></div>
    <div class="card"><div class="kpi-label">Conv. Iniciadas</div><div class="kpi-val" id="mk-conv" style="color:var(--green)">{fmt_n(d30["conversas"])}</div></div>
    <div class="card"><div class="kpi-label">Conexões Msg</div><div class="kpi-val" id="mk-conx" style="color:var(--sub)">{fmt_n(d30["conexoes"])}</div></div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Gasto & Cliques Diários</div>
    <canvas id="chartMetaDiario2" height="180"></canvas>
  </div>

  <!-- Tabela campanhas -->
  <div class="card">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">Campanhas — últimos 30 dias</div>
      <span class="badge badge-gray">dados fixos em 30d · calendário afeta KPIs e gráficos</span>
    </div>
    <div style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th>Campanha</th>
            <th style="text-align:right">Gasto</th>
            <th style="text-align:right">Impressões</th>
            <th style="text-align:right">Cliques</th>
            <th style="text-align:right">CTR</th>
            <th style="text-align:right">CPC</th>
            <th style="text-align:right" title="conversation_started_7d">Msg. Iniciadas</th>
            <th style="text-align:right" title="Gasto ÷ mensagens iniciadas">Custo/Msg</th>
            <th style="text-align:right" title="omni_add_to_cart">Adic. Carrinho</th>
            <th style="text-align:right" title="Gasto ÷ adições ao carrinho">Custo/Carrinho</th>
          </tr>
        </thead>
        <tbody id="camps-body"></tbody>
      </table>
    </div>
  </div>

  <!-- Criativos -->
  <div class="card mt-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">🎨 Criativos — últimos 30 dias</div>
      <span class="badge badge-gray">agrupado por tipo · clique no grupo para minimizar</span>
    </div>
    <div id="criativos-content" style="overflow-x:auto">
      <table>
        <thead>
          <tr>
            <th style="width:140px">ID Criativo</th>
            <th>Nome do Anúncio</th>
            <th style="text-align:right">Impressões</th>
            <th style="text-align:right">CTR</th>
            <th style="text-align:right">CPC</th>
            <th style="text-align:right" title="Custo por mensagem (MSG) ou por adição ao carrinho (CONV/TRAF)">Custo/Resultado</th>
            <th style="text-align:right">Resultados</th>
          </tr>
        </thead>
        <tbody id="criativos-body"></tbody>
      </table>
    </div>
  </div>

</div><!-- /tab-meta -->


<!-- ═══════════════════════════ REZDY ════════════════════════════════════ -->
<div id="tab-rezdy" class="tab-content pt-3" style="display:none">

  <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-5">
    <div class="card"><div class="kpi-label">Total Reservas</div><div class="kpi-val" id="rk-total">{rz["total"]}</div></div>
    <div class="card"><div class="kpi-label">Confirmadas</div><div class="kpi-val" id="rk-conf" style="color:var(--green)">{rz["confirmadas"]}</div></div>
    <div class="card"><div class="kpi-label">Voos Realizados</div><div class="kpi-val" id="rk-fulfilments" style="color:var(--cyan)">{rz["fulfilments"]}</div><div class="kpi-delta">pelo dia do voo</div></div>
    <div class="card"><div class="kpi-label">Abandonadas</div><div class="kpi-val" id="rk-aband" style="color:var(--red)">{rz["abandonadas"]}</div></div>
    <div class="card"><div class="kpi-label">Receita</div><div class="kpi-val" id="rk-receita" style="color:var(--green);font-size:1.2rem">{fmt_brl(rz["receita"])}</div></div>
    <div class="card"><div class="kpi-label">Ticket Médio</div><div class="kpi-val" id="rk-ticket" style="font-size:1.3rem">{fmt_brl(rz["ticket_medio"])}</div></div>
    <div class="card"><div class="kpi-label">Taxa Conversão</div><div class="kpi-val" id="rk-taxa" style="color:var(--cyan)">{fmt_pct(rz["taxa_conv"])}</div></div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Reservas por Dia</div><canvas id="chartRezdyDiario2" height="200"></canvas></div>
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Receita Diária Confirmada</div><canvas id="chartRezdyReceita" height="200"></canvas></div>
  </div>

  <!-- Booking vs Fulfilment -->
  <div class="card mb-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">Dia da Reserva vs Dia do Voo (Fulfilment)</div>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
          <span style="display:inline-block;width:12px;height:12px;background:rgba(99,102,241,.65);border-radius:2px"></span>Reservas feitas
        </span>
        <span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
          <span style="display:inline-block;width:22px;height:2px;background:#06b6d4;border-radius:2px"></span>Voos realizados
        </span>
      </div>
    </div>
    <canvas id="chartBookingVsFulfilment" height="190"></canvas>
  </div>

  <!-- Heatmap: mês da reserva × mês do voo -->
  <div class="card mb-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">📅 Quando Reservaram → Para Qual Mês Voaram?</div>
      <span class="badge badge-gray">linhas = mês da reserva · colunas = mês do voo · cor = volume</span>
    </div>
    <div style="overflow-x:auto">
      <div id="heatmap-container"></div>
    </div>
  </div>

  <!-- Público: Top Países -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🌍 Público — Top Países</div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>País</th>
            <th style="text-align:right">Bookings</th>
            <th style="text-align:right">PAX</th>
            <th style="text-align:right">Receita</th>
            <th style="text-align:right">% Bookings</th>
          </tr></thead>
          <tbody id="paises-body"></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🏆 Maiores Clientes (por receita)</div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Cliente</th>
            <th>País</th>
            <th style="text-align:right">Bookings</th>
            <th style="text-align:right">PAX</th>
            <th style="text-align:right">Total Gasto</th>
          </tr></thead>
          <tbody id="top-clientes-body"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Por Produto</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Produto</th><th style="text-align:right">Ordens</th><th style="text-align:right">Confirmadas</th><th style="text-align:right">Receita</th><th style="text-align:right">Tx Conv.</th></tr></thead>
        <tbody id="prod-body"></tbody>
      </table>
    </div>
  </div>

  <!-- ── Voos Confirmados via Cupom (dinâmico) ──────────────────────────── -->
  <div class="card mb-5" id="cupom-section">
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <div style="font-weight:600;font-size:.9rem">Voos Confirmados via Cupom</div>
      <span class="badge badge-blue" id="cupom-count">—</span>
    </div>

    <div id="cupom-vazio" style="display:none;color:#94a3b8;font-size:.85rem;padding:8px 0">
      Nenhum voo confirmado com cupom no período selecionado.
    </div>

    <div id="cupom-tabelas">
      <div style="font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Resumo por cupom</div>
      <div style="overflow-x:auto;margin-bottom:20px">
        <table>
          <thead><tr>
            <th>Cupom</th>
            <th style="text-align:right">Voos Conf.</th>
            <th style="text-align:right">Receita Total</th>
            <th style="text-align:right">Ticket Médio</th>
            <th>Produto Principal</th>
          </tr></thead>
          <tbody id="cupom-resumo-body"></tbody>
        </table>
      </div>

      <div style="font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Detalhe por voo</div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Nº Pedido</th><th>Cupom</th><th>Produto</th>
            <th style="text-align:right">Pax</th>
            <th style="text-align:right">Valor</th>
            <th>Reservado</th><th>Voo</th><th>Cliente</th>
          </tr></thead>
          <tbody id="cupom-detail-body"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ── Últimas Reservas ────────────────────────────────────────────────── -->
  <div class="card">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Últimas Reservas</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Nº Pedido</th><th>Status</th><th>Produto</th>
          <th style="text-align:right">PAX</th>
          <th style="text-align:right">Valor</th>
          <th>Reservado em</th><th>Voo em</th>
          <th>Fonte</th><th>País</th>
        </tr></thead>
        <tbody id="book-body"></tbody>
      </table>
    </div>
  </div>

</div><!-- /tab-rezdy -->

</main>

<footer class="border-t" style="border-color:var(--border);padding:20px 24px;text-align:center;font-size:.73rem;color:var(--sub)">
  Vertical Rio Marketing Dashboard · Meta Ads Graph API + Rezdy API · {atualizado_em}
</footer>

<!-- ═══════════════════════════ DATA ══════════════════════════════════════ -->
<script>
const META_DATA    = {meta_json};
const REZDY_DATA   = {rezdy_json};
const CAMPS_DIARIO = {camps_diario_json};
const BOOKINGS     = {bookings_json};
const HEATMAP      = {heatmap_json};
const CRIATIVOS    = {criativos_json};
const VOOS_CUPOM   = {voos_cupom_json};
const HOJE         = "{hoje_str}";
const D30_FROM     = "{d30_str}";
const D90_FROM     = "{d90_str}";

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fBRL = v => 'R$ ' + Number(v).toLocaleString('pt-BR',{{minimumFractionDigits:2,maximumFractionDigits:2}});
const fN   = v => Math.round(v).toLocaleString('pt-BR');
const fPct = v => Number(v).toFixed(2) + '%';

function setText(id, val) {{
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}}

// ─── Tab switching ────────────────────────────────────────────────────────────
function switchTab(tab, btn) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).style.display = 'block';
  if (btn) btn.classList.add('active');
}}

// ─── Chart registry ───────────────────────────────────────────────────────────
const charts = {{}};
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

function makeChart(id, config) {{
  const ctx = document.getElementById(id);
  if (!ctx) return null;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, config);
  return charts[id];
}}

function updateChart(id, labels, datasetsData) {{
  const c = charts[id];
  if (!c) return;
  c.data.labels = labels;
  datasetsData.forEach((data, i) => {{ c.data.datasets[i].data = data; }});
  c.update('none');
}}

// ─── Chart builders ───────────────────────────────────────────────────────────
function buildMetaDiario(canvasId, mDays) {{
  const labels = mDays.map(d => d.data.slice(5));
  makeChart(canvasId, {{
    type: 'bar',
    data: {{
      labels,
      datasets: [
        {{ label:'Gasto (R$)', data:mDays.map(d=>d.gasto), backgroundColor:'rgba(99,102,241,.7)', borderRadius:3, yAxisID:'y', order:2 }},
        {{ label:'Cliques', data:mDays.map(d=>d.cliques), type:'line', borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,.1)', fill:true, tension:0.4, pointRadius:2, yAxisID:'y1', order:1 }},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{
        y:{{position:'left', grid:{{color:'rgba(51,65,85,.4)'}}, ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}},
        y1:{{position:'right', grid:{{drawOnChartArea:false}}}},
        x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:12}}}}
      }}
    }}
  }});
}}

function buildRezdyDiario(canvasId, rDays) {{
  const labels = rDays.map(d => d.data.slice(5));
  makeChart(canvasId, {{
    type:'bar',
    data:{{
      labels,
      datasets:[
        {{label:'Confirmadas', data:rDays.map(d=>d.confirmadas), backgroundColor:'rgba(34,197,94,.75)', borderRadius:3, stack:'s'}},
        {{label:'Abandonadas', data:rDays.map(d=>d.abandonadas), backgroundColor:'rgba(239,68,68,.5)',  borderRadius:3, stack:'s'}},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:12}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}}}}}}
    }}
  }});
}}

function buildRezdyReceita(canvasId, rDays) {{
  makeChart(canvasId, {{
    type:'line',
    data:{{
      labels: rDays.map(d=>d.data.slice(5)),
      datasets:[{{label:'Receita Confirmada (R$)', data:rDays.map(d=>d.receita), borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,.1)', fill:true, tension:0.4, pointRadius:2}}]
    }},
    options:{{
      responsive:true,
      plugins:{{legend:{{labels:{{boxWidth:12}}}},tooltip:{{callbacks:{{label:ctx=>fBRL(ctx.raw)}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:12}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}}}}
    }}
  }});
}}

function buildBookingVsFulfilment(canvasId, from, to) {{
  // Gera array de todas as datas do intervalo
  const dates = [];
  const cur = new Date(from + 'T12:00:00');
  const end = new Date(to   + 'T12:00:00');
  while (cur <= end) {{ dates.push(cur.toISOString().slice(0,10)); cur.setDate(cur.getDate()+1); }}

  // Agrupa por data da reserva e por data do voo
  const bookMap = {{}};
  const fulfMap = {{}};
  for (const b of BOOKINGS) {{
    if (b.s !== 'CONFIRMED') continue;
    if (b.d >= from && b.d <= to)         bookMap[b.d] = (bookMap[b.d]||0) + 1;
    if (b.t && b.t >= from && b.t <= to)  fulfMap[b.t] = (fulfMap[b.t]||0) + 1;
  }}

  makeChart(canvasId, {{
    type: 'bar',
    data: {{
      labels: dates.map(d => d.slice(5)),
      datasets: [
        {{ label:'Reservas feitas', data:dates.map(d=>bookMap[d]||0),
           backgroundColor:'rgba(99,102,241,.65)', borderRadius:3, order:2 }},
        {{ label:'Voos realizados (fulfilment)', data:dates.map(d=>fulfMap[d]||0),
           type:'line', borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,.12)',
           fill:true, tension:0.4, pointRadius:2, borderWidth:2, order:1 }},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}}}},
      scales:{{
        x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:14}}}},
        y:{{grid:{{color:'rgba(51,65,85,.4)'}}, beginAtZero:true, ticks:{{stepSize:1}}}}
      }}
    }}
  }});
}}

// ─── Date range apply ─────────────────────────────────────────────────────────
function applyDateRange(from, to) {{
  // ── Filter Meta ──
  const mDays  = META_DATA.diario.filter(d => d.data >= from && d.data <= to);
  const mGasto = mDays.reduce((s,d)=>s+d.gasto,0);
  const mImpr  = mDays.reduce((s,d)=>s+d.impressoes,0);
  const mClick = mDays.reduce((s,d)=>s+d.cliques,0);
  const mConv  = mDays.reduce((s,d)=>s+(d.conversas||0),0);
  const mConx  = mDays.reduce((s,d)=>s+(d.conexoes||0),0);
  const mCtr   = mImpr  ? mClick/mImpr*100  : 0;
  const mCpc   = mClick ? mGasto/mClick     : 0;
  const mCpm   = mImpr  ? mGasto/mImpr*1000 : 0;

  // ── Filter Rezdy ──
  const rDays  = REZDY_DATA.por_dia.filter(d => d.data >= from && d.data <= to);
  const rConf  = rDays.reduce((s,d)=>s+d.confirmadas,0);
  const rAband = rDays.reduce((s,d)=>s+d.abandonadas,0);
  const rOutras= rDays.reduce((s,d)=>s+(d.outras||0),0);
  const rTotal = rConf + rAband + rOutras;
  const rRec   = rDays.reduce((s,d)=>s+d.receita,0);
  const rTick  = rConf ? rRec/rConf : 0;
  const rTaxa  = rTotal ? rConf/rTotal*100 : 0;

  // ── Update Visão Geral KPIs ──
  setText('vg-gasto', fBRL(mGasto));
  setText('vg-impr',  fN(mImpr));
  setText('vg-ctr',   fPct(mCtr));
  setText('vg-cpc',   fBRL(mCpc));
  setText('vg-receita', fBRL(rRec));
  setText('vg-conf',    rConf);
  setText('vg-conf-sub', rTotal + ' total (' + fPct(rTaxa) + ' conv.)');
  setText('vg-ticket',  fBRL(rTick));
  setText('vg-aband',   rAband);
  setText('vg-aband-sub', 'de ' + rTotal + ' reservas');

  // ── Update Funil ──
  setText('fn-impr',  fN(mImpr));
  setText('fn-click', fN(mClick));
  setText('fn-ctr-lbl', fPct(mCtr) + ' CTR');
  setText('fn-total', rTotal);
  setText('fn-conf',  rConf);
  setText('fn-taxa-lbl', fPct(rTaxa) + ' taxa');

  // ── Update Meta Ads KPIs ──
  setText('mk-gasto', fBRL(mGasto));
  setText('mk-impr',  fN(mImpr));
  setText('mk-click', fN(mClick));
  setText('mk-ctr',   fPct(mCtr));
  setText('mk-cpc',   fBRL(mCpc));
  setText('mk-cpm',   fBRL(mCpm));
  setText('mk-conv',  fN(mConv));
  setText('mk-conx',  fN(mConx));

  // ── Update Rezdy KPIs ──
  setText('rk-total',  rTotal);
  setText('rk-conf',   rConf);
  setText('rk-aband',  rAband);
  setText('rk-receita',fBRL(rRec));
  setText('rk-ticket', fBRL(rTick));
  setText('rk-taxa',   fPct(rTaxa));
  // Voos realizados: confirmados cujo dia do voo (tour_date) cai no período selecionado
  const rFulfilments = BOOKINGS.filter(b => b.s === 'CONFIRMED' && b.t && b.t >= from && b.t <= to && b.t <= HOJE).length;
  setText('rk-fulfilments', rFulfilments);

  // ── Update charts ──
  buildMetaDiario('chartMetaDiario', mDays);
  buildMetaDiario('chartMetaDiario2', mDays);
  buildRezdyDiario('chartRezdyDiario', rDays);
  buildRezdyDiario('chartRezdyDiario2', rDays);
  buildRezdyReceita('chartRezdyReceita', rDays);
  buildBookingVsFulfilment('chartBookingVsFulfilment', from, to);

  // ── Tabelas e gráficos dinâmicos ──
  renderCampanhas(from, to);
  renderProdutos(from, to);
  renderBookings(from, to);
  renderPaises(from, to);
  renderCupons(from, to);

  // ── Range label ──
  const days = Math.round((new Date(to) - new Date(from)) / 86400000) + 1;
  setText('range-label', days + ' dias selecionados');
}}

// ─── Render dinâmico de campanhas, produtos e bookings ───────────────────────

function renderCampanhas(from, to) {{
  const agg = {{}};
  for (const camp of CAMPS_DIARIO) {{
    agg[camp.id] = {{nome: camp.nome, g:0, i:0, c:0, m:0, a:0}};
    for (const [data, d] of Object.entries(camp.daily)) {{
      if (data >= from && data <= to) {{
        agg[camp.id].g += d.g; agg[camp.id].i += d.i;
        agg[camp.id].c += d.c; agg[camp.id].m += d.m; agg[camp.id].a += d.a;
      }}
    }}
  }}
  const camps = Object.values(agg).filter(c=>c.g>0).sort((a,b)=>b.g-a.g);
  const tbody = document.getElementById('camps-body');
  if (!tbody) return;
  tbody.innerHTML = camps.map(c => {{
    const tipo = c.nome.includes('[MSG]')?'MSG':c.nome.includes('[CONV]')?'CONV':'TRAF';
    const tc   = tipo==='CONV'?'#6366f1':tipo==='MSG'?'#22c55e':'#06b6d4';
    const ctr  = c.i ? c.c/c.i*100 : 0;
    const cpc  = c.c ? c.g/c.c     : 0;
    const cm   = c.m ? c.g/c.m     : 0;
    const ca   = c.a ? c.g/c.a     : 0;
    return `<tr>
      <td><span style="font-size:.65rem;font-weight:700;padding:1px 6px;border-radius:4px;background:${{tc}}22;color:${{tc}};margin-right:6px">${{tipo}}</span><span style="font-weight:500">${{c.nome.slice(0,55)}}</span></td>
      <td style="text-align:right;color:#6366f1;font-weight:600">${{fBRL(c.g)}}</td>
      <td style="text-align:right">${{fN(c.i)}}</td>
      <td style="text-align:right">${{fN(c.c)}}</td>
      <td style="text-align:right;color:#06b6d4">${{ctr.toFixed(2)}}%</td>
      <td style="text-align:right">${{fBRL(cpc)}}</td>
      <td style="text-align:right;color:#22c55e;font-weight:600">${{fN(c.m)}}</td>
      <td style="text-align:right;color:#94a3b8">${{cm ? fBRL(cm) : '—'}}</td>
      <td style="text-align:right;color:#6366f1;font-weight:600">${{fN(c.a)}}</td>
      <td style="text-align:right;color:#94a3b8">${{ca ? fBRL(ca) : '—'}}</td>
    </tr>`;
  }}).join('');

  // Gráfico gasto por campanha
  const top7 = camps.slice(0,7);
  makeChart('chartCampanhas',{{
    type:'bar',
    data:{{labels:top7.map(c=>c.nome.slice(0,35)),datasets:[{{label:'Gasto (R$)',data:top7.map(c=>c.g),backgroundColor:'rgba(99,102,241,.75)',borderRadius:4}}]}},
    options:{{indexAxis:'y',responsive:true,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>fBRL(ctx.raw)}}}}}},scales:{{x:{{grid:{{color:'rgba(51,65,85,.4)'}},ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}},y:{{grid:{{display:false}}}}}}}}
  }});
}}

function renderProdutos(from, to) {{
  const bk = BOOKINGS.filter(b => b.d >= from && b.d <= to);
  const prods = {{}};
  for (const b of bk) {{
    if (!prods[b.p]) prods[b.p] = {{o:0, conf:0, rec:0}};
    prods[b.p].o++;
    prods[b.p].rec += b.v;
    if (b.s === 'CONFIRMED') prods[b.p].conf++;
  }}
  const lista = Object.entries(prods).sort((a,b)=>b[1].rec-a[1].rec);
  const tbody = document.getElementById('prod-body');
  if (tbody) tbody.innerHTML = lista.map(([nome,p])=>{{
    const tx = p.o ? (p.conf/p.o*100).toFixed(1) : 0;
    return `<tr><td style="font-weight:500">${{nome}}</td><td style="text-align:right">${{p.o}}</td><td style="text-align:right"><span class="badge badge-green">${{p.conf}}</span></td><td style="text-align:right;color:#22c55e">${{fBRL(p.rec)}}</td><td style="text-align:right">${{tx}}%</td></tr>`;
  }}).join('');

  // Gráfico donut de produtos
  const top8 = lista.slice(0,8);
  makeChart('chartProdutos',{{
    type:'doughnut',
    data:{{labels:top8.map(([n])=>n.slice(0,30)),datasets:[{{data:top8.map(([,p])=>p.rec),backgroundColor:['#6366f1','#22c55e','#06b6d4','#f59e0b','#ec4899','#8b5cf6','#14b8a6','#f97316'],borderWidth:0,hoverOffset:6}}]}},
    options:{{responsive:true,plugins:{{legend:{{position:'right',labels:{{boxWidth:12,padding:12}}}},tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fBRL(ctx.raw)}}}}}}}}
  }});
}}

const _criativosCollapsed = {{MSG:false, CONV:false, TRAF:false}};

function toggleCriativosTipo(tipo) {{
  _criativosCollapsed[tipo] = !_criativosCollapsed[tipo];
  const rows  = document.querySelectorAll(`[data-criativos="${{tipo}}"]`);
  const icon  = document.getElementById(`criativos-icon-${{tipo}}`);
  const label = document.getElementById(`criativos-label-${{tipo}}`);
  const hidden = _criativosCollapsed[tipo];
  rows.forEach(r => r.style.display = hidden ? 'none' : '');
  if (icon)  icon.textContent  = hidden ? '▼' : '▲';
  if (label) label.textContent = hidden ? 'Expandir' : 'Minimizar';
}}

function renderCriativos() {{
  const TIPO_COLOR = {{MSG:'#22c55e', CONV:'#6366f1', TRAF:'#06b6d4'}};
  const TIPO_LABEL = {{MSG:'Mensagens', CONV:'Conversão / Carrinho', TRAF:'Tráfego'}};

  const grupos = {{MSG:[], CONV:[], TRAF:[]}};
  for (const a of CRIATIVOS) {{
    const t = a.camp.includes('[MSG]') ? 'MSG' : a.camp.includes('[CONV]') ? 'CONV' : 'TRAF';
    grupos[t].push({{...a, tipo:t}});
  }}

  let html = '';
  for (const tipo of ['MSG','CONV','TRAF']) {{
    const ads = grupos[tipo];
    if (!ads.length) continue;
    const tc      = TIPO_COLOR[tipo];
    const hidden  = _criativosCollapsed[tipo];
    html += `<tr style="background:rgba(99,102,241,.07);cursor:pointer" onclick="toggleCriativosTipo('${{tipo}}')">
      <td colspan="7" style="padding:10px 12px">
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span style="font-weight:700;font-size:.72rem;color:${{tc}};letter-spacing:.06em;text-transform:uppercase">
            ${{TIPO_LABEL[tipo]}} &nbsp;·&nbsp; ${{ads.length}} criativos
          </span>
          <span style="font-size:.7rem;color:#94a3b8;display:flex;align-items:center;gap:4px;user-select:none">
            <span id="criativos-icon-${{tipo}}">${{hidden ? '▼' : '▲'}}</span>
            <span id="criativos-label-${{tipo}}">${{hidden ? 'Expandir' : 'Minimizar'}}</span>
          </span>
        </div>
      </td>
    </tr>`;
    for (const a of ads) {{
      const isMsg      = tipo === 'MSG';
      const resultado  = isMsg ? a.msg : a.cart;
      const custo_res  = resultado ? fBRL(a.gasto / resultado) : '—';
      const res_label  = resultado ? `${{resultado}} ${{isMsg ? 'msg' : 'cart'}}` : '—';
      html += `<tr data-criativos="${{tipo}}" style="${{hidden ? 'display:none' : ''}}">
        <td style="font-family:monospace;font-size:.7rem;color:#94a3b8;white-space:nowrap">${{a.id}}</td>
        <td style="font-size:.82rem;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${{a.nome}}">${{a.nome.slice(0,55)}}</td>
        <td style="text-align:right">${{fN(a.impr)}}</td>
        <td style="text-align:right;color:#06b6d4">${{a.ctr.toFixed(2)}}%</td>
        <td style="text-align:right">${{fBRL(a.cpc)}}</td>
        <td style="text-align:right;color:#22c55e;font-weight:600">${{custo_res}}</td>
        <td style="text-align:right;color:#94a3b8;font-size:.78rem">${{res_label}}</td>
      </tr>`;
    }}
  }}
  const el = document.getElementById('criativos-body');
  if (el) el.innerHTML = html;
}}

// ─── Cupons dinâmicos ────────────────────────────────────────────────────────
function renderCupons(from, to) {{
  const filtered = VOOS_CUPOM.filter(b => b.data >= from && b.data <= to);

  // Agrega por cupom
  const agr = {{}};
  for (const b of filtered) {{
    if (!agr[b.coupon]) agr[b.coupon] = {{ usos:0, receita:0, produtos:{{}} }};
    agr[b.coupon].usos    += 1;
    agr[b.coupon].receita += b.valor;
    agr[b.coupon].produtos[b.produto] = (agr[b.coupon].produtos[b.produto] || 0) + 1;
  }}

  const resumoList = Object.entries(agr)
    .map(([cupom, d]) => ({{
      cupom,
      usos:     d.usos,
      receita:  d.receita,
      ticket:   d.usos ? d.receita / d.usos : 0,
      produto_top: Object.entries(d.produtos).sort((a,b)=>b[1]-a[1])[0]?.[0] || '—',
    }}))
    .sort((a, b) => b.usos - a.usos);

  // Atualiza badge
  const badge = document.getElementById('cupom-count');
  if (badge) badge.textContent = filtered.length + ' voos · ' + resumoList.length + ' cupons';

  // Mostra/oculta seções
  const vazio   = document.getElementById('cupom-vazio');
  const tabelas = document.getElementById('cupom-tabelas');
  if (filtered.length === 0) {{
    if (vazio)   vazio.style.display   = 'block';
    if (tabelas) tabelas.style.display = 'none';
    return;
  }}
  if (vazio)   vazio.style.display   = 'none';
  if (tabelas) tabelas.style.display = 'block';

  // Resumo por cupom
  const resumoBody = document.getElementById('cupom-resumo-body');
  if (resumoBody) {{
    resumoBody.innerHTML = resumoList.map(cr => `
      <tr>
        <td><span class="badge badge-blue" style="font-size:.82rem;padding:3px 10px">${{cr.cupom}}</span></td>
        <td style="text-align:right;font-weight:700;color:#22c55e">${{cr.usos}}</td>
        <td style="text-align:right;color:#22c55e;font-weight:600">${{fBRL(cr.receita)}}</td>
        <td style="text-align:right">${{fBRL(cr.ticket)}}</td>
        <td style="color:#94a3b8;font-size:.8rem">${{cr.produto_top.slice(0,45)}}</td>
      </tr>`).join('');
  }}

  // Detalhe por voo
  const detailBody = document.getElementById('cupom-detail-body');
  if (detailBody) {{
    detailBody.innerHTML = filtered.map(b => `
      <tr>
        <td style="font-family:monospace;font-size:.78rem">${{b.numero}}</td>
        <td><span class="badge badge-blue">${{b.coupon}}</span></td>
        <td style="font-weight:500;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{b.produto}}</td>
        <td style="text-align:right">${{b.pax || '—'}}</td>
        <td style="text-align:right;color:#22c55e;font-weight:600">${{fBRL(b.valor)}}</td>
        <td style="color:#94a3b8">${{b.data}}</td>
        <td style="color:#94a3b8">${{b.tour_dt || '—'}}</td>
        <td style="color:#94a3b8;font-size:.8rem;max-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{b.nome}}</td>
      </tr>`).join('');
  }}
}}

function renderBookings(from, to) {{
  const tbody = document.getElementById('book-body');
  if (!tbody) return;
  const rows = BOOKINGS.filter(b => b.d >= from && b.d <= to).slice(0,200);
  tbody.innerHTML = rows.map(b => {{
    const sc  = b.s==='CONFIRMED'?'badge-green':b.s==='ABANDONED_CART'?'badge-red':'badge-amber';
    const flag = countryFlag(b.cc);
    return `<tr>
      <td style="font-family:monospace;font-size:.78rem">${{b.n}}</td>
      <td><span class="badge ${{sc}}">${{b.s.replace(/_/g,' ')}}</span></td>
      <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{b.p}}</td>
      <td style="text-align:right;color:#94a3b8">${{b.px||1}}</td>
      <td style="text-align:right;font-weight:500">${{fBRL(b.v)}}</td>
      <td style="color:#94a3b8">${{b.d}}</td>
      <td style="color:#06b6d4">${{b.t||'—'}}</td>
      <td style="font-size:.75rem;color:#94a3b8">${{b.f}}</td>
      <td style="font-size:.8rem" title="${{b.cc}}">${{flag}} ${{b.cc}}</td>
    </tr>`;
  }}).join('');
}}

function countryFlag(cc) {{
  if (!cc || cc.length !== 2) return '';
  return cc.toUpperCase().replace(/./g, c =>
    String.fromCodePoint(0x1F1E6 - 65 + c.charCodeAt(0)));
}}

function renderPaises(from, to) {{
  const bk = BOOKINGS.filter(b => b.d >= from && b.d <= to && b.s === 'CONFIRMED');
  const paises = {{}};
  let totalBookings = 0;
  for (const b of bk) {{
    const cc = b.cc || '??';
    if (!paises[cc]) paises[cc] = {{ordens:0, pax:0, receita:0}};
    paises[cc].ordens++;
    paises[cc].pax += (b.px || 1);
    paises[cc].receita += b.v;
    totalBookings++;
  }}
  const sorted = Object.entries(paises).sort((a,b) => b[1].ordens - a[1].ordens).slice(0,20);
  const tbody = document.getElementById('paises-body');
  if (!tbody) return;
  tbody.innerHTML = sorted.map(([cc, v]) => {{
    const flag = countryFlag(cc);
    const pct  = totalBookings ? (v.ordens/totalBookings*100).toFixed(1) : '0.0';
    return `<tr>
      <td><span style="margin-right:4px">${{flag}}</span>${{cc.toUpperCase()}}</td>
      <td style="text-align:right;font-weight:600">${{v.ordens}}</td>
      <td style="text-align:right;color:#94a3b8">${{v.pax}}</td>
      <td style="text-align:right">${{fBRL(v.receita)}}</td>
      <td style="text-align:right">
        <div style="display:flex;align-items:center;gap:6px;justify-content:flex-end">
          <div style="background:#6366f1;height:6px;border-radius:3px;width:${{Math.round(parseFloat(pct)*.8)}}px"></div>
          ${{pct}}%
        </div>
      </td>
    </tr>`;
  }}).join('');

  // Top clientes
  const clientes = {{}};
  for (const b of bk) {{
    const k = b.n.slice(0,4) + '…'; // anonimizado por pedido
  }}
  // Agrega por hash simples da ordem (top 15 por receita)
  const clienteMap = {{}};
  for (const b of BOOKINGS.filter(x => x.d >= from && x.d <= to && x.s === 'CONFIRMED')) {{
    const key = b.n;
    if (!clienteMap[key]) clienteMap[key] = {{n: b.n, cc: b.cc, ordens:0, pax:0, receita:0}};
    clienteMap[key].ordens++;
    clienteMap[key].pax   += (b.px||1);
    clienteMap[key].receita += b.v;
  }}
  // Rezdy: cada booking é 1 cliente, mas repetidos têm mesmo orderNumber
  // Top por receita
  const topCli = Object.values(clienteMap).sort((a,b)=>b.receita-a.receita).slice(0,15);
  const tbody2 = document.getElementById('top-clientes-body');
  if (tbody2) {{
    tbody2.innerHTML = topCli.map((c,i) => {{
      const flag = countryFlag(c.cc);
      return `<tr>
        <td style="font-family:monospace;font-size:.78rem">${{c.n}}</td>
        <td><span style="margin-right:4px">${{flag}}</span>${{c.cc||'??'}}</td>
        <td style="text-align:right">${{c.ordens}}</td>
        <td style="text-align:right;color:#94a3b8">${{c.pax}}</td>
        <td style="text-align:right;font-weight:600;color:#22c55e">${{fBRL(c.receita)}}</td>
      </tr>`;
    }}).join('');
  }}
}}

function renderHeatmap() {{
  const MONTHS_PT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const allCreated = Object.keys(HEATMAP).sort();
  // Collect all tour months
  const tourSet = new Set();
  for (const row of Object.values(HEATMAP)) Object.keys(row).forEach(m => tourSet.add(m));
  const allTour = [...tourSet].sort();
  if (!allCreated.length) return;

  // Max for color scale
  let maxVal = 0;
  for (const row of Object.values(HEATMAP))
    for (const v of Object.values(row)) if (v > maxVal) maxVal = v;

  const fmtYM = ym => {{
    const [y,m] = ym.split('-');
    return MONTHS_PT[parseInt(m)-1] + '/' + y.slice(2);
  }};
  const heatColor = v => {{
    if (!v) return 'background:#1e293b;color:#334155';
    const t = v / maxVal;
    const r = Math.round(30 + t * 79);
    const g = Math.round(41 + t * 60);
    const b = Math.round(99 + t * 156);
    const fg = t > 0.5 ? '#fff' : '#c4b5fd';
    return `background:rgb(${{r}},${{g}},${{b}});color:${{fg}};font-weight:${{t>0.3?'600':'400'}}`;
  }};

  let tbl = '<table style="border-collapse:separate;border-spacing:2px;font-size:.72rem;min-width:max-content">';
  // Header row
  tbl += '<thead><tr>';
  tbl += '<th style="padding:4px 10px;text-align:left;color:#94a3b8;font-weight:500">Reservou em ↓ Voou em →</th>';
  for (const tm of allTour) {{
    tbl += `<th style="padding:4px 8px;text-align:center;color:#94a3b8;font-weight:500;white-space:nowrap">${{fmtYM(tm)}}</th>`;
  }}
  tbl += '</tr></thead><tbody>';
  for (const cm of allCreated) {{
    tbl += `<tr><td style="padding:4px 10px;color:#94a3b8;white-space:nowrap;font-weight:500">${{fmtYM(cm)}}</td>`;
    for (const tm of allTour) {{
      const v = (HEATMAP[cm] || {{}})[tm] || 0;
      tbl += `<td style="padding:6px 8px;text-align:center;border-radius:4px;${{heatColor(v)}};min-width:44px">${{v||''}}</td>`;
    }}
    tbl += '</tr>';
  }}
  tbl += '</tbody></table>';
  const el = document.getElementById('heatmap-container');
  if (el) el.innerHTML = tbl;
}}

// ─── Init flatpickr ───────────────────────────────────────────────────────────
flatpickr.localize(flatpickr.l10ns.pt);
flatpickr("#date-range", {{
  mode: "range",
  dateFormat: "Y-m-d",
  altInput: true,
  altFormat: "d/m/Y",
  defaultDate: [D30_FROM, HOJE],
  minDate: D90_FROM,
  maxDate: HOJE,
  disableMobile: true,
  onChange: function(dates) {{
    if (dates.length === 2) {{
      const fmt = d => d.toISOString().slice(0,10);
      applyDateRange(fmt(dates[0]), fmt(dates[1]));
    }}
  }}
}});

// ─── Init com últimos 30d ─────────────────────────────────────────────────────
applyDateRange(D30_FROM, HOJE);
renderCriativos();
renderHeatmap();
</script>
</body>
</html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Vertical Rio Dashboard — {agora} ===\n")

    print("[ 1/7 ] Meta Ads — resumo 30d (API)...")
    d30 = buscar_meta_periodo("last_30d")
    print(f"       Gasto R${d30['gasto']:,.2f} | CTR {d30['ctr']}% | Conv.Inic. {d30['conversas']}")

    print("[ 2/7 ] Meta Ads — campanhas 30d...")
    campanhas = buscar_meta_campanhas("last_30d")
    print(f"       {len(campanhas)} campanhas")

    print("[ 3/7 ] Meta Ads — diario conta 90d...")
    diario = buscar_meta_diario(90)
    print(f"       {len(diario)} dias")

    print("[ 4/7 ] Meta Ads — diário por campanha 90d...")
    camps_diario = buscar_meta_diario_campanhas(90)
    print(f"       {len(camps_diario)} campanhas × 90d")

    print("[ 5/7 ] Meta Ads — criativos 30d...")
    criativos = buscar_meta_criativos("last_30d")
    print(f"       {len(criativos)} criativos ativos")

    print("[ 6/7 ] Rezdy — reservas...")
    reservas = buscar_rezdy_reservas(3000)
    print(f"       {len(reservas)} reservas")

    print("[ 7/7 ] Processando e gerando HTML...")
    rezdy_dados = processar_rezdy(reservas, dias=90)
    print(f"       90d: {rezdy_dados['confirmadas']} conf | R${rezdy_dados['receita']:,.2f} | {len(rezdy_dados['todos_bookings'])} bookings")

    meta = {"d30": d30, "campanhas": campanhas, "diario": diario}
    html = gerar_html(meta, rezdy_dados, camps_diario, criativos, agora)

    with open(ARQUIVO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nOK: {ARQUIVO_HTML} gerado ({len(html):,} chars)")


if __name__ == "__main__":
    main()
