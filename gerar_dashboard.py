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
        "conexoes":    0,   # total_messaging_connection
        "first_reply": 0,   # messaging_first_reply
        "conversas":   0,   # conversation_started_7d  ← mensagens iniciadas
        "bloqueios":   0,   # messaging_block
        "compras":     0,
        "valor_compras": 0.0,
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
            "conexoes":    acoes["conexoes"],
            "first_reply": acoes["first_reply"],
            "conversas":   acoes["conversas"],   # ← mensagens iniciadas
            "bloqueios":   acoes["bloqueios"],
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
    corte    = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    recentes = [b for b in reservas if (b.get("dateCreated") or "")[:10] >= corte]

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

    hoje = datetime.now()
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

    tabela = []
    for b in sorted(recentes, key=lambda x: x.get("dateCreated", ""), reverse=True)[:150]:
        itens   = b.get("items", [])
        produto = itens[0].get("productName", "-") if itens else "-"
        tabela.append({
            "numero":  b.get("orderNumber", ""),
            "status":  b.get("status", ""),
            "produto": produto,
            "valor":   float(b.get("totalAmount", 0) or 0),
            "data":    (b.get("dateCreated") or "")[:10],
            "fonte":   (b.get("source") or "ONLINE").upper(),
            "coupon":  b.get("coupon") or "",
        })

    return {
        "total":        len(recentes),
        "confirmadas":  confirmadas_total,
        "abandonadas":  abandonadas_total,
        "outras":       len(recentes) - confirmadas_total - abandonadas_total,
        "receita":      receita_total,
        "ticket_medio": ticket_medio,
        "taxa_conv":    taxa_conv,
        "por_dia":      todos_dias,
        "por_status":   dict(por_status),
        "por_produto":  produtos_lista,
        "por_fonte":    {k: {"ordens": v["ordens"], "receita": round(v["receita"], 2)}
                         for k, v in por_fonte.items()},
        "tabela":       tabela,
    }


# ─── HTML ─────────────────────────────────────────────────────────────────────
def gerar_html(meta, rezdy_dados, atualizado_em):
    d30 = meta["d30"]
    rz  = rezdy_dados

    meta_json  = json.dumps(meta,       ensure_ascii=False)
    rezdy_json = json.dumps(rz,         ensure_ascii=False)
    camps_json = json.dumps(meta["campanhas"], ensure_ascii=False)

    prod_nomes   = json.dumps([p["produto"][:30] for p in rz["por_produto"][:8]])
    prod_receita = json.dumps([p["receita"]       for p in rz["por_produto"][:8]])
    camp_nomes   = json.dumps([c["nome"][:35]     for c in meta["campanhas"][:7]])
    camp_gastos  = json.dumps([c["gasto"]         for c in meta["campanhas"][:7]])

    hoje_str   = datetime.now().strftime("%Y-%m-%d")
    d30_str    = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
    d90_str    = (datetime.now() - timedelta(days=89)).strftime("%Y-%m-%d")

    def fmt_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    def fmt_n(v):   return f"{int(v):,}".replace(",", ".")
    def fmt_pct(v): return f"{v:.2f}%"

    camps_rows = ""
    for c in meta["campanhas"]:
        # Badge de tipo: MSG vs outros
        tipo = "MSG" if "[MSG]" in c["nome"] else ("CONV" if "[CONV]" in c["nome"] else "TRAF")
        tipo_color = "#6366f1" if tipo == "CONV" else ("#22c55e" if tipo == "MSG" else "#06b6d4")
        camps_rows += f"""<tr>
          <td>
            <span style="font-size:0.65rem;font-weight:700;padding:1px 6px;border-radius:4px;background:{tipo_color}22;color:{tipo_color};margin-right:6px">{tipo}</span>
            <span style="font-weight:500">{c["nome"][:55]}</span>
          </td>
          <td style="text-align:right;color:#6366f1;font-weight:600">{fmt_brl(c["gasto"])}</td>
          <td style="text-align:right">{fmt_n(c["impressoes"])}</td>
          <td style="text-align:right">{fmt_n(c["cliques"])}</td>
          <td style="text-align:right;color:#06b6d4">{c["ctr"]:.2f}%</td>
          <td style="text-align:right">{fmt_brl(c["cpc"])}</td>
          <td style="text-align:right;color:#22c55e;font-weight:600">{fmt_n(c["conversas"])}</td>
          <td style="text-align:right;color:#94a3b8">{fmt_n(c["conexoes"])}</td>
          <td style="text-align:right;color:#f59e0b">{fmt_n(c["bloqueios"])}</td>
        </tr>"""

    prod_rows = ""
    for p in rz["por_produto"]:
        tx = round(p["confirmadas"] / p["ordens"] * 100, 1) if p["ordens"] else 0
        prod_rows += f"""<tr>
          <td style="font-weight:500">{p["produto"]}</td>
          <td style="text-align:right">{p["ordens"]}</td>
          <td style="text-align:right"><span class="badge badge-green">{p["confirmadas"]}</span></td>
          <td style="text-align:right;color:#22c55e">{fmt_brl(p["receita"])}</td>
          <td style="text-align:right">{tx:.1f}%</td>
        </tr>"""

    book_rows = ""
    for b in rz["tabela"]:
        st_class = ("badge-green" if b["status"] == "CONFIRMED"
                    else "badge-red" if b["status"] == "ABANDONED_CART"
                    else "badge-amber")
        coupon_html = (f'<span class="badge badge-blue">{b["coupon"]}</span>'
                       if b["coupon"] else "")
        book_rows += f"""<tr>
          <td style="font-family:monospace;font-size:0.78rem">{b["numero"]}</td>
          <td><span class="badge {st_class}">{b["status"].replace("_"," ")}</span></td>
          <td style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{b["produto"]}</td>
          <td style="text-align:right;font-weight:500">{fmt_brl(b["valor"])}</td>
          <td style="color:#94a3b8">{b["data"]}</td>
          <td style="font-size:0.75rem;color:#94a3b8">{b["fonte"]}</td>
          <td>{coupon_html}</td>
        </tr>"""

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
            <th style="text-align:right" title="Conversas iniciadas (conversation_started_7d)">Conv. Iniciadas</th>
            <th style="text-align:right" title="Total messaging connections">Conexões</th>
            <th style="text-align:right" title="Bloqueios de mensagem">Bloqueios</th>
          </tr>
        </thead>
        <tbody>{camps_rows}</tbody>
      </table>
    </div>
  </div>

</div><!-- /tab-meta -->


<!-- ═══════════════════════════ REZDY ════════════════════════════════════ -->
<div id="tab-rezdy" class="tab-content pt-3" style="display:none">

  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
    <div class="card"><div class="kpi-label">Total Reservas</div><div class="kpi-val" id="rk-total">{rz["total"]}</div></div>
    <div class="card"><div class="kpi-label">Confirmadas</div><div class="kpi-val" id="rk-conf" style="color:var(--green)">{rz["confirmadas"]}</div></div>
    <div class="card"><div class="kpi-label">Abandonadas</div><div class="kpi-val" id="rk-aband" style="color:var(--red)">{rz["abandonadas"]}</div></div>
    <div class="card"><div class="kpi-label">Receita</div><div class="kpi-val" id="rk-receita" style="color:var(--green);font-size:1.3rem">{fmt_brl(rz["receita"])}</div></div>
    <div class="card"><div class="kpi-label">Ticket Médio</div><div class="kpi-val" id="rk-ticket" style="font-size:1.4rem">{fmt_brl(rz["ticket_medio"])}</div></div>
    <div class="card"><div class="kpi-label">Taxa Conversão</div><div class="kpi-val" id="rk-taxa" style="color:var(--cyan)">{fmt_pct(rz["taxa_conv"])}</div></div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Reservas por Dia</div><canvas id="chartRezdyDiario2" height="200"></canvas></div>
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Receita Diária Confirmada</div><canvas id="chartRezdyReceita" height="200"></canvas></div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Por Produto</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Produto</th><th style="text-align:right">Ordens</th><th style="text-align:right">Confirmadas</th><th style="text-align:right">Receita</th><th style="text-align:right">Tx Conv.</th></tr></thead>
        <tbody>{prod_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Últimas Reservas</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Nº Pedido</th><th>Status</th><th>Produto</th><th style="text-align:right">Valor</th><th>Data</th><th>Fonte</th><th>Cupom</th></tr></thead>
        <tbody>{book_rows}</tbody>
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
const META_DATA  = {meta_json};
const REZDY_DATA = {rezdy_json};
const CAMPS_DATA = {camps_json};
const HOJE       = "{hoje_str}";
const D30_FROM   = "{d30_str}";
const D90_FROM   = "{d90_str}";

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

  // ── Update charts ──
  const mLabels = mDays.map(d=>d.data.slice(5));
  buildMetaDiario('chartMetaDiario', mDays);
  buildMetaDiario('chartMetaDiario2', mDays);
  buildRezdyDiario('chartRezdyDiario', rDays);
  buildRezdyDiario('chartRezdyDiario2', rDays);
  buildRezdyReceita('chartRezdyReceita', rDays);

  // ── Range label ──
  const days = Math.round((new Date(to) - new Date(from)) / 86400000) + 1;
  setText('range-label', days + ' dias selecionados');
}}

// ─── Produtos + Campanhas (estáticos) ─────────────────────────────────────────
makeChart('chartProdutos', {{
  type:'doughnut',
  data:{{
    labels: {prod_nomes},
    datasets:[{{data:{prod_receita}, backgroundColor:['#6366f1','#22c55e','#06b6d4','#f59e0b','#ec4899','#8b5cf6','#14b8a6','#f97316'], borderWidth:0, hoverOffset:6}}]
  }},
  options:{{
    responsive:true,
    plugins:{{
      legend:{{position:'right',labels:{{boxWidth:12,padding:12}}}},
      tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fBRL(ctx.raw)}}}}
    }}
  }}
}});

makeChart('chartCampanhas', {{
  type:'bar',
  data:{{
    labels:{camp_nomes},
    datasets:[{{label:'Gasto (R$)', data:{camp_gastos}, backgroundColor:'rgba(99,102,241,.75)', borderRadius:4}}]
  }},
  options:{{
    indexAxis:'y', responsive:true,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>fBRL(ctx.raw)}}}}}},
    scales:{{x:{{grid:{{color:'rgba(51,65,85,.4)'}},ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}},y:{{grid:{{display:false}}}}}}
  }}
}});

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
</script>
</body>
</html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Vertical Rio Dashboard — {agora} ===\n")

    print("[ 1/5 ] Meta Ads — resumo 30d (API)...")
    d30 = buscar_meta_periodo("last_30d")
    print(f"       Gasto R${d30['gasto']:,.2f} | CTR {d30['ctr']}% | Conv.Inic. {d30['conversas']}")

    print("[ 2/5 ] Meta Ads — campanhas 30d...")
    campanhas = buscar_meta_campanhas("last_30d")
    print(f"       {len(campanhas)} campanhas")
    for c in campanhas:
        print(f"       {c['nome'][:50]:50s} | Conv.Inic.: {c['conversas']:3d} | Conexoes: {c['conexoes']:3d} | Bloq: {c['bloqueios']}")

    print("[ 3/5 ] Meta Ads — diario 90d...")
    diario = buscar_meta_diario(90)
    print(f"       {len(diario)} dias")

    print("[ 4/5 ] Rezdy — reservas...")
    reservas = buscar_rezdy_reservas(800)
    print(f"       {len(reservas)} reservas")

    print("[ 5/5 ] Processando e gerando HTML...")
    rezdy_dados = processar_rezdy(reservas, dias=90)
    print(f"       90d: {rezdy_dados['confirmadas']} conf | R${rezdy_dados['receita']:,.2f}")

    meta = {"d30": d30, "campanhas": campanhas, "diario": diario}
    html = gerar_html(meta, rezdy_dados, agora)

    with open(ARQUIVO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nOK: {ARQUIVO_HTML} gerado ({len(html):,} chars)")


if __name__ == "__main__":
    main()
