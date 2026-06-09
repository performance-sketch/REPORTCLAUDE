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
    out = {"mensagens": 0, "conversas": 0, "compras": 0, "valor_compras": 0.0}
    for a in (actions or []):
        at, v = a.get("action_type", ""), float(a.get("value", 0) or 0)
        if "messaging_connection" in at or "messaging_first_reply" in at:
            out["mensagens"] += int(v)
        if "conversation_started" in at:
            out["conversas"] += int(v)
        if at in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"):
            out["compras"] += int(v)
    for a in (actions or []):
        at, v = a.get("action_type", ""), float(a.get("value", 0) or 0)
        if at in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"):
            out["valor_compras"] += v
    return out


def buscar_meta_periodo(preset):
    fields = "spend,impressions,clicks,reach,cpc,ctr,cpm,actions"
    resp = meta_get(f"{META_ACCOUNT}/insights", {
        "level": "account", "fields": fields, "date_preset": preset, "limit": 1,
    })
    row = (resp.get("data") or [{}])[0]
    spend   = float(row.get("spend", 0) or 0)
    impr    = int(row.get("impressions", 0) or 0)
    clicks  = int(row.get("clicks", 0) or 0)
    reach   = int(row.get("reach", 0) or 0)
    acoes   = _extrair_acoes(row.get("actions"))
    return {
        "gasto":       round(spend, 2),
        "impressoes":  impr,
        "cliques":     clicks,
        "alcance":     reach,
        "ctr":         round(float(row.get("ctr", 0) or 0), 2),
        "cpc":         round(float(row.get("cpc", 0) or 0), 2) if row.get("cpc") else round(spend/clicks, 2) if clicks else 0,
        "cpm":         round(float(row.get("cpm", 0) or 0), 2),
        "mensagens":   acoes["mensagens"],
        "conversas":   acoes["conversas"],
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
        spend  = float(c.get("spend", 0) or 0)
        acoes  = _extrair_acoes(c.get("actions"))
        resultado.append({
            "nome":      c.get("campaign_name", "?"),
            "id":        c.get("campaign_id", ""),
            "gasto":     round(spend, 2),
            "impressoes":int(c.get("impressions", 0) or 0),
            "cliques":   int(c.get("clicks", 0) or 0),
            "ctr":       round(float(c.get("ctr", 0) or 0), 2),
            "cpc":       round(float(c.get("cpc", 0) or 0), 2) if c.get("cpc") else 0,
            "alcance":   int(c.get("reach", 0) or 0),
            "mensagens": acoes["mensagens"],
            "conversas": acoes["conversas"],
        })
    resultado.sort(key=lambda x: x["gasto"], reverse=True)
    return resultado


def buscar_meta_diario(dias=30):
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
        "limit": 100,
    })
    dados = _paginar(resp)
    resultado = []
    for d in dados:
        spend = float(d.get("spend", 0) or 0)
        acoes = _extrair_acoes(d.get("actions"))
        resultado.append({
            "data":      d.get("date_start", ""),
            "gasto":     round(spend, 2),
            "impressoes":int(d.get("impressions", 0) or 0),
            "cliques":   int(d.get("clicks", 0) or 0),
            "mensagens": acoes["mensagens"],
        })
    return sorted(resultado, key=lambda x: x["data"])


# ─── Rezdy ────────────────────────────────────────────────────────────────────
def buscar_rezdy_reservas(limite_total=600):
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


def processar_rezdy(reservas, dias=30):
    corte = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    recentes = [b for b in reservas if (b.get("dateCreated") or "")[:10] >= corte]

    por_dia    = defaultdict(lambda: {"confirmadas": 0, "abandonadas": 0, "outras": 0, "receita": 0.0})
    por_produto= defaultdict(lambda: {"ordens": 0, "confirmadas": 0, "receita": 0.0})
    por_status = defaultdict(int)
    por_fonte  = defaultdict(lambda: {"ordens": 0, "receita": 0.0})

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

    # últimos `dias` dias ordenados
    todos_dias = []
    for i in range(dias):
        d = (datetime.now() - timedelta(days=dias - 1 - i)).strftime("%Y-%m-%d")
        v = por_dia[d]
        todos_dias.append({"data": d, **{k: round(v[k], 2) if k == "receita" else v[k] for k in v}})

    confirmadas_total = sum(b["confirmadas"] for b in todos_dias)
    abandonadas_total = sum(b["abandonadas"] for b in todos_dias)
    receita_total     = round(sum(b["receita"] for b in todos_dias), 2)
    ticket_medio      = round(receita_total / confirmadas_total, 2) if confirmadas_total else 0
    taxa_conv         = round(confirmadas_total / len(recentes) * 100, 1) if recentes else 0

    produtos_lista = sorted(
        [{"produto": k, **{kk: round(v[kk], 2) if kk == "receita" else v[kk] for kk in v}}
         for k, v in por_produto.items()],
        key=lambda x: x["receita"], reverse=True
    )

    tabela = []
    for b in sorted(recentes, key=lambda x: x.get("dateCreated", ""), reverse=True)[:100]:
        itens   = b.get("items", [])
        produto = itens[0].get("productName", "-") if itens else "-"
        coupon  = b.get("coupon") or ""
        tabela.append({
            "numero":  b.get("orderNumber", ""),
            "status":  b.get("status", ""),
            "produto": produto,
            "valor":   float(b.get("totalAmount", 0) or 0),
            "data":    (b.get("dateCreated") or "")[:10],
            "fonte":   (b.get("source") or "ONLINE").upper(),
            "coupon":  coupon,
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
    d7  = meta["d7"]
    d14 = meta["d14"]
    d30 = meta["d30"]
    rz  = rezdy_dados

    meta_json  = json.dumps(meta,       ensure_ascii=False)
    rezdy_json = json.dumps(rz,         ensure_ascii=False)
    camps_json = json.dumps(meta["campanhas"], ensure_ascii=False)

    # Etiquetas e labels para os charts
    dias_labels = json.dumps([d["data"][5:] for d in meta["diario"]])  # MM-DD
    dias_gasto  = json.dumps([d["gasto"]    for d in meta["diario"]])
    dias_clicks = json.dumps([d["cliques"]  for d in meta["diario"]])

    rz_dias_labels = json.dumps([d["data"][5:]        for d in rz["por_dia"]])
    rz_confirmadas = json.dumps([d["confirmadas"]     for d in rz["por_dia"]])
    rz_abandonadas = json.dumps([d["abandonadas"]     for d in rz["por_dia"]])
    rz_receita_dia = json.dumps([d["receita"]         for d in rz["por_dia"]])

    prod_nomes   = json.dumps([p["produto"][:30]  for p in rz["por_produto"][:8]])
    prod_receita = json.dumps([p["receita"]        for p in rz["por_produto"][:8]])

    camp_nomes   = json.dumps([c["nome"][:35] for c in meta["campanhas"][:6]])
    camp_gastos  = json.dumps([c["gasto"]     for c in meta["campanhas"][:6]])

    def fmt_brl(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    def fmt_n(v):   return f"{int(v):,}".replace(",", ".")
    def fmt_pct(v): return f"{v:.2f}%"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vertical Rio — Marketing Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --surface2: #263248;
    --border: #334155; --text: #f1f5f9; --sub: #94a3b8;
    --indigo: #6366f1; --green: #22c55e; --amber: #f59e0b;
    --red: #ef4444; --cyan: #06b6d4;
  }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
  .kpi-val {{ font-size: 1.75rem; font-weight: 700; line-height: 1.1; }}
  .kpi-label {{ font-size: 0.75rem; color: var(--sub); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }}
  .kpi-delta {{ font-size: 0.78rem; margin-top: 4px; }}
  .tab-btn {{ padding: 8px 18px; border-radius: 8px; font-size: 0.875rem; font-weight: 500; cursor: pointer; border: none; transition: all .15s; }}
  .tab-btn.active {{ background: var(--indigo); color: #fff; }}
  .tab-btn:not(.active) {{ background: var(--surface2); color: var(--sub); }}
  .tab-btn:hover:not(.active) {{ background: var(--border); color: var(--text); }}
  .period-btn {{ padding: 4px 14px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; border: 1px solid var(--border); transition: all .15s; }}
  .period-btn.active {{ background: var(--indigo); border-color: var(--indigo); color: #fff; }}
  .period-btn:not(.active) {{ background: transparent; color: var(--sub); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 0.7rem; font-weight: 600; }}
  .badge-green  {{ background: rgba(34,197,94,.15); color: #22c55e; }}
  .badge-red    {{ background: rgba(239,68,68,.15); color: #ef4444; }}
  .badge-amber  {{ background: rgba(245,158,11,.15); color: #f59e0b; }}
  .badge-gray   {{ background: rgba(148,163,184,.1); color: #94a3b8; }}
  .badge-blue   {{ background: rgba(99,102,241,.15); color: #818cf8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ color: var(--sub); font-weight: 500; text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid rgba(51,65,85,.5); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: rgba(99,102,241,.04); }}
  .funnel-bar {{ height: 40px; border-radius: 6px; display: flex; align-items: center; padding: 0 14px; font-weight: 600; font-size: 0.85rem; margin-bottom: 8px; }}
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
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
        <div style="font-weight:700;font-size:1rem;line-height:1.1;">Vertical Rio</div>
        <div style="font-size:0.7rem;color:var(--sub);">Marketing Dashboard</div>
      </div>
    </div>
    <div class="flex items-center gap-4">
      <div style="font-size:0.75rem;color:var(--sub);">
        <span style="color:var(--green)">●</span> Atualizado em <strong style="color:var(--text)">{atualizado_em}</strong>
      </div>
    </div>
  </div>
</header>

<!-- TABS NAV -->
<div class="max-w-screen-xl mx-auto px-6 pt-5 pb-1 flex gap-2 flex-wrap">
  <button class="tab-btn active" onclick="switchTab('visao')">Visão Geral</button>
  <button class="tab-btn" onclick="switchTab('meta')">Meta Ads</button>
  <button class="tab-btn" onclick="switchTab('rezdy')">Rezdy Bookings</button>
</div>

<main class="max-w-screen-xl mx-auto px-6 pb-12">

<!-- ═══════════════════════════════════════════════════════════ VISÃO GERAL -->
<div id="tab-visao" class="tab-content pt-5">

  <!-- KPIs Meta -->
  <div class="mb-2" style="font-size:0.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em;">Meta Ads — últimos 30 dias</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
    <div class="card">
      <div class="kpi-label">Gasto</div>
      <div class="kpi-val" style="color:var(--indigo)">{fmt_brl(d30["gasto"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Impressões</div>
      <div class="kpi-val">{fmt_n(d30["impressoes"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">CTR</div>
      <div class="kpi-val" style="color:var(--cyan)">{fmt_pct(d30["ctr"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">CPC Médio</div>
      <div class="kpi-val">{fmt_brl(d30["cpc"])}</div>
    </div>
  </div>

  <!-- KPIs Rezdy -->
  <div class="mb-2" style="font-size:0.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em;">Rezdy — últimos 30 dias</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
    <div class="card">
      <div class="kpi-label">Receita Confirmada</div>
      <div class="kpi-val" style="color:var(--green)">{fmt_brl(rz["receita"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Reservas Confirmadas</div>
      <div class="kpi-val">{rz["confirmadas"]}</div>
      <div class="kpi-delta" style="color:var(--sub)">{rz["total"]} total ({fmt_pct(rz["taxa_conv"])} conversão)</div>
    </div>
    <div class="card">
      <div class="kpi-label">Ticket Médio</div>
      <div class="kpi-val">{fmt_brl(rz["ticket_medio"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Abandonadas</div>
      <div class="kpi-val" style="color:var(--red)">{rz["abandonadas"]}</div>
      <div class="kpi-delta" style="color:var(--sub)">de {rz["total"]} reservas</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Gasto & Cliques Diários — 30 dias</div>
      <canvas id="chartMetaDiario" height="200"></canvas>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Reservas por Dia — 30 dias</div>
      <canvas id="chartRezdyDiario" height="200"></canvas>
    </div>
  </div>

  <!-- Funnel -->
  <div class="card mb-6">
    <div style="font-weight:600;font-size:0.9rem;margin-bottom:20px;">Funil: Meta Ads → Rezdy</div>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
      <div style="text-align:center;">
        <div style="font-size:1.6rem;font-weight:700;color:var(--indigo)">{fmt_n(d30["impressoes"])}</div>
        <div style="font-size:0.75rem;color:var(--sub);margin-top:2px;">Impressões</div>
        <div style="width:100%;height:4px;background:var(--indigo);border-radius:2px;margin-top:8px;opacity:.6;"></div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:1.6rem;font-weight:700;color:var(--cyan)">{fmt_n(d30["cliques"])}</div>
        <div style="font-size:0.75rem;color:var(--sub);margin-top:2px;">Cliques</div>
        <div style="font-size:0.7rem;color:var(--cyan);margin-top:2px;">{fmt_pct(d30["ctr"])} CTR</div>
        <div style="width:100%;height:4px;background:var(--cyan);border-radius:2px;margin-top:6px;opacity:.6;"></div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:1.6rem;font-weight:700;color:var(--amber)">{rz["total"]}</div>
        <div style="font-size:0.75rem;color:var(--sub);margin-top:2px;">Reservas Geradas</div>
        <div style="font-size:0.7rem;color:var(--amber);margin-top:2px;">{round(rz["total"]/d30["cliques"]*100,2) if d30["cliques"] else 0:.2f}% dos cliques</div>
        <div style="width:100%;height:4px;background:var(--amber);border-radius:2px;margin-top:6px;opacity:.6;"></div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:1.6rem;font-weight:700;color:var(--green)">{rz["confirmadas"]}</div>
        <div style="font-size:0.75rem;color:var(--sub);margin-top:2px;">Confirmadas</div>
        <div style="font-size:0.7rem;color:var(--green);margin-top:2px;">{fmt_pct(rz["taxa_conv"])} taxa</div>
        <div style="width:100%;height:4px;background:var(--green);border-radius:2px;margin-top:6px;opacity:.6;"></div>
      </div>
    </div>
  </div>

  <!-- Receita por Produto -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Receita por Produto (30d)</div>
      <canvas id="chartProdutos" height="220"></canvas>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Gasto por Campanha (30d)</div>
      <canvas id="chartCampanhas" height="220"></canvas>
    </div>
  </div>

</div><!-- /tab-visao -->


<!-- ═══════════════════════════════════════════════════════════ META ADS -->
<div id="tab-meta" class="tab-content pt-5" style="display:none">

  <!-- Period selector -->
  <div class="flex items-center gap-2 mb-5">
    <span style="font-size:0.8rem;color:var(--sub);">Período:</span>
    <button class="period-btn active" onclick="switchPeriodo('d7',this)">7 dias</button>
    <button class="period-btn" onclick="switchPeriodo('d14',this)">14 dias</button>
    <button class="period-btn" onclick="switchPeriodo('d30',this)">30 dias</button>
  </div>

  <!-- KPIs dinâmicos -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" id="meta-kpis">
    <!-- preenchido por JS -->
  </div>

  <!-- Gráfico diário -->
  <div class="card mb-5">
    <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Gasto Diário — últimos 30 dias</div>
    <canvas id="chartMetaDiario2" height="180"></canvas>
  </div>

  <!-- Tabela de campanhas -->
  <div class="card">
    <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Campanhas — últimos 30 dias</div>
    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>Campanha</th>
            <th style="text-align:right">Gasto</th>
            <th style="text-align:right">Impressões</th>
            <th style="text-align:right">Cliques</th>
            <th style="text-align:right">CTR</th>
            <th style="text-align:right">CPC</th>
            <th style="text-align:right">Mensagens</th>
          </tr>
        </thead>
        <tbody id="table-campanhas"></tbody>
      </table>
    </div>
  </div>

</div><!-- /tab-meta -->


<!-- ═══════════════════════════════════════════════════════════ REZDY -->
<div id="tab-rezdy" class="tab-content pt-5" style="display:none">

  <!-- KPIs Rezdy -->
  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
    <div class="card">
      <div class="kpi-label">Total Reservas</div>
      <div class="kpi-val">{rz["total"]}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Confirmadas</div>
      <div class="kpi-val" style="color:var(--green)">{rz["confirmadas"]}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Abandonadas</div>
      <div class="kpi-val" style="color:var(--red)">{rz["abandonadas"]}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Receita</div>
      <div class="kpi-val" style="color:var(--green);font-size:1.3rem">{fmt_brl(rz["receita"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Ticket Médio</div>
      <div class="kpi-val" style="font-size:1.4rem">{fmt_brl(rz["ticket_medio"])}</div>
    </div>
    <div class="card">
      <div class="kpi-label">Taxa Conversão</div>
      <div class="kpi-val" style="color:var(--cyan)">{fmt_pct(rz["taxa_conv"])}</div>
    </div>
  </div>

  <!-- Gráfico reservas + receita -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Reservas por Dia</div>
      <canvas id="chartRezdyDiario2" height="200"></canvas>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Receita Diária Confirmada</div>
      <canvas id="chartRezdyReceita" height="200"></canvas>
    </div>
  </div>

  <!-- Tabela por produto -->
  <div class="card mb-5">
    <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Por Produto</div>
    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>Produto</th>
            <th style="text-align:right">Ordens</th>
            <th style="text-align:right">Confirmadas</th>
            <th style="text-align:right">Receita</th>
            <th style="text-align:right">Tx Conv.</th>
          </tr>
        </thead>
        <tbody>
          {''.join(f"""<tr>
            <td style="font-weight:500">{p["produto"]}</td>
            <td style="text-align:right">{p["ordens"]}</td>
            <td style="text-align:right"><span class="badge badge-green">{p["confirmadas"]}</span></td>
            <td style="text-align:right;color:var(--green)">{fmt_brl(p["receita"])}</td>
            <td style="text-align:right">{round(p["confirmadas"]/p["ordens"]*100,1) if p["ordens"] else 0:.1f}%</td>
          </tr>""" for p in rz["por_produto"])}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Tabela bookings recentes -->
  <div class="card">
    <div style="font-weight:600;font-size:0.9rem;margin-bottom:16px;">Últimas 100 Reservas</div>
    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>Nº Pedido</th>
            <th>Status</th>
            <th>Produto</th>
            <th style="text-align:right">Valor</th>
            <th>Data</th>
            <th>Fonte</th>
            <th>Cupom</th>
          </tr>
        </thead>
        <tbody>
          {''.join(f"""<tr>
            <td style="font-family:monospace;font-size:0.78rem">{b["numero"]}</td>
            <td><span class="badge {
              'badge-green' if b['status']=='CONFIRMED'
              else 'badge-red' if b['status']=='ABANDONED_CART'
              else 'badge-amber'
            }">{b["status"].replace("_"," ")}</span></td>
            <td style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{b["produto"]}</td>
            <td style="text-align:right;font-weight:500">{fmt_brl(b["valor"])}</td>
            <td style="color:var(--sub)">{b["data"]}</td>
            <td style="font-size:0.75rem;color:var(--sub)">{b["fonte"]}</td>
            <td>{f'<span class="badge badge-blue">{b["coupon"]}</span>' if b["coupon"] else ""}</td>
          </tr>""" for b in rz["tabela"])}
        </tbody>
      </table>
    </div>
  </div>

</div><!-- /tab-rezdy -->

</main>

<!-- FOOTER -->
<footer class="border-t" style="border-color:var(--border);padding:20px 24px;text-align:center;font-size:0.73rem;color:var(--sub);">
  Vertical Rio Marketing Dashboard · Dados ao vivo via Meta Ads Graph API + Rezdy API · {atualizado_em}
</footer>

<!-- DATA + JS -->
<script>
const META_DATA  = {meta_json};
const REZDY_DATA = {rezdy_json};
const CAMPS_DATA = {camps_json};

// ─── Tab switching ────────────────────────────────────────────────────────────
function switchTab(tab) {{
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).style.display = 'block';
  event.target.classList.add('active');
  if (tab === 'meta' && !window._metaChartInit) {{ initMetaCharts(); window._metaChartInit = true; }}
  if (tab === 'rezdy' && !window._rezdyChartInit) {{ initRezdyCharts2(); window._rezdyChartInit = true; }}
}}

// ─── Period switching ─────────────────────────────────────────────────────────
let periodoAtual = 'd7';
function switchPeriodo(p, btn) {{
  periodoAtual = p;
  document.querySelectorAll('.period-btn').forEach(el => el.classList.remove('active'));
  btn.classList.add('active');
  renderMetaKPIs(p);
}}

function renderMetaKPIs(p) {{
  const d = META_DATA[p];
  const fmtBrl = v => 'R$ ' + v.toLocaleString('pt-BR', {{minimumFractionDigits:2,maximumFractionDigits:2}});
  const fmtN   = v => parseInt(v).toLocaleString('pt-BR');
  const kpis = [
    {{ label:'Gasto', val: fmtBrl(d.gasto),      color:'#6366f1' }},
    {{ label:'Impressões', val: fmtN(d.impressoes), color:'#f1f5f9' }},
    {{ label:'Alcance', val: fmtN(d.alcance),     color:'#f1f5f9' }},
    {{ label:'Cliques', val: fmtN(d.cliques),     color:'#f1f5f9' }},
    {{ label:'CTR', val: d.ctr.toFixed(2)+'%',   color:'#06b6d4' }},
    {{ label:'CPC', val: fmtBrl(d.cpc),           color:'#f1f5f9' }},
    {{ label:'CPM', val: fmtBrl(d.cpm),           color:'#f1f5f9' }},
    {{ label:'Mensagens', val: fmtN(d.mensagens), color:'#22c55e' }},
  ];
  document.getElementById('meta-kpis').innerHTML = kpis.map(k => `
    <div class="card">
      <div class="kpi-label">${{k.label}}</div>
      <div class="kpi-val" style="color:${{k.color}};font-size:1.4rem">${{k.val}}</div>
    </div>`).join('');
}}

// ─── Campanhas table ──────────────────────────────────────────────────────────
function renderCampanhas() {{
  const fmtBrl = v => 'R$ ' + v.toLocaleString('pt-BR', {{minimumFractionDigits:2,maximumFractionDigits:2}});
  const fmtN   = v => parseInt(v).toLocaleString('pt-BR');
  document.getElementById('table-campanhas').innerHTML = CAMPS_DATA.map(c => `
    <tr>
      <td style="font-weight:500;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{c.nome}}</td>
      <td style="text-align:right;color:#6366f1;font-weight:600">${{fmtBrl(c.gasto)}}</td>
      <td style="text-align:right">${{fmtN(c.impressoes)}}</td>
      <td style="text-align:right">${{fmtN(c.cliques)}}</td>
      <td style="text-align:right;color:#06b6d4">${{c.ctr.toFixed(2)}}%</td>
      <td style="text-align:right">${{fmtBrl(c.cpc)}}</td>
      <td style="text-align:right;color:#22c55e">${{fmtN(c.mensagens)}}</td>
    </tr>`).join('');
}}

// ─── Chart defaults ───────────────────────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';
Chart.defaults.font.family = 'system-ui, sans-serif';

const LABELS_DIAS  = {dias_labels};
const GASTO_DIAS   = {dias_gasto};
const CLICKS_DIAS  = {dias_clicks};
const RZ_LABELS    = {rz_dias_labels};
const RZ_CONF      = {rz_confirmadas};
const RZ_ABAND     = {rz_abandonadas};
const RZ_RECEITA   = {rz_receita_dia};
const PROD_NOMES   = {prod_nomes};
const PROD_RECEITA = {prod_receita};
const CAMP_NOMES   = {camp_nomes};
const CAMP_GASTOS  = {camp_gastos};

// ─── Visão Geral charts ───────────────────────────────────────────────────────
new Chart(document.getElementById('chartMetaDiario'), {{
  type: 'bar',
  data: {{
    labels: LABELS_DIAS,
    datasets: [
      {{
        label: 'Gasto (R$)', data: GASTO_DIAS,
        backgroundColor: 'rgba(99,102,241,.7)', yAxisID: 'y',
        borderRadius: 4, order: 2,
      }},
      {{
        label: 'Cliques', data: CLICKS_DIAS, type: 'line',
        borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,.1)',
        fill: true, tension: 0.4, pointRadius: 2, yAxisID: 'y1', order: 1,
      }},
    ]
  }},
  options: {{
    responsive: true, interaction: {{ mode:'index', intersect:false }},
    plugins: {{ legend: {{ labels: {{ boxWidth:12 }} }} }},
    scales: {{
      y:  {{ position:'left',  grid:{{color:'rgba(51,65,85,.4)'}}, ticks:{{callback: v => 'R$'+v.toLocaleString('pt-BR')}} }},
      y1: {{ position:'right', grid:{{drawOnChartArea:false}} }},
      x:  {{ grid:{{display:false}}, ticks:{{maxTicksLimit:10}} }}
    }}
  }}
}});

new Chart(document.getElementById('chartRezdyDiario'), {{
  type: 'bar',
  data: {{
    labels: RZ_LABELS,
    datasets: [
      {{ label:'Confirmadas', data:RZ_CONF,  backgroundColor:'rgba(34,197,94,.75)', borderRadius:3, stack:'s' }},
      {{ label:'Abandonadas', data:RZ_ABAND, backgroundColor:'rgba(239,68,68,.5)',  borderRadius:3, stack:'s' }},
    ]
  }},
  options: {{
    responsive: true, interaction:{{mode:'index', intersect:false}},
    plugins:{{ legend:{{ labels:{{boxWidth:12}} }} }},
    scales: {{
      x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:10}}}},
      y:{{grid:{{color:'rgba(51,65,85,.4)'}}}}
    }}
  }}
}});

new Chart(document.getElementById('chartProdutos'), {{
  type: 'doughnut',
  data: {{
    labels: PROD_NOMES,
    datasets: [{{ data:PROD_RECEITA,
      backgroundColor:['#6366f1','#22c55e','#06b6d4','#f59e0b','#ec4899','#8b5cf6','#14b8a6','#f97316'],
      borderWidth:0, hoverOffset:6,
    }}]
  }},
  options: {{
    responsive:true,
    plugins:{{ legend:{{ position:'right', labels:{{boxWidth:12, padding:12}} }},
      tooltip:{{ callbacks:{{ label: ctx => ctx.label + ': R$ ' + ctx.raw.toLocaleString('pt-BR', {{minimumFractionDigits:2}}) }} }}
    }}
  }}
}});

new Chart(document.getElementById('chartCampanhas'), {{
  type: 'bar',
  data: {{
    labels: CAMP_NOMES,
    datasets: [{{ label:'Gasto (R$)', data:CAMP_GASTOS,
      backgroundColor:'rgba(99,102,241,.75)', borderRadius:4,
    }}]
  }},
  options: {{
    indexAxis:'y', responsive:true,
    plugins:{{ legend:{{display:false}},
      tooltip:{{ callbacks:{{ label: ctx => 'R$ ' + ctx.raw.toLocaleString('pt-BR', {{minimumFractionDigits:2}}) }} }}
    }},
    scales:{{ x:{{ grid:{{color:'rgba(51,65,85,.4)'}}, ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}} }}, y:{{grid:{{display:false}}}} }}
  }}
}});

// ─── Meta Ads tab charts ──────────────────────────────────────────────────────
function initMetaCharts() {{
  renderMetaKPIs('d7');
  renderCampanhas();
  new Chart(document.getElementById('chartMetaDiario2'), {{
    type:'bar',
    data:{{
      labels:LABELS_DIAS,
      datasets:[
        {{ label:'Gasto (R$)', data:GASTO_DIAS, backgroundColor:'rgba(99,102,241,.7)', borderRadius:4, order:2, yAxisID:'y' }},
        {{ label:'Cliques', data:CLICKS_DIAS, type:'line', borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,.1)', fill:true, tension:0.4, pointRadius:2, yAxisID:'y1', order:1 }},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index', intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{
        y:{{position:'left', grid:{{color:'rgba(51,65,85,.4)'}}, ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}},
        y1:{{position:'right', grid:{{drawOnChartArea:false}}}},
        x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:10}}}}
      }}
    }}
  }});
}}

// ─── Rezdy tab charts ─────────────────────────────────────────────────────────
function initRezdyCharts2() {{
  new Chart(document.getElementById('chartRezdyDiario2'), {{
    type:'bar',
    data:{{
      labels:RZ_LABELS,
      datasets:[
        {{label:'Confirmadas', data:RZ_CONF,  backgroundColor:'rgba(34,197,94,.75)', borderRadius:3, stack:'s'}},
        {{label:'Abandonadas', data:RZ_ABAND, backgroundColor:'rgba(239,68,68,.5)',  borderRadius:3, stack:'s'}},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index', intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:10}}}}, y:{{grid:{{color:'rgba(51,65,85,.4)'}}}}}}
    }}
  }});
  new Chart(document.getElementById('chartRezdyReceita'), {{
    type:'line',
    data:{{
      labels:RZ_LABELS,
      datasets:[{{
        label:'Receita Confirmada (R$)', data:RZ_RECEITA,
        borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,.1)',
        fill:true, tension:0.4, pointRadius:2,
      }}]
    }},
    options:{{
      responsive:true,
      plugins:{{legend:{{labels:{{boxWidth:12}}}},
        tooltip:{{callbacks:{{label:ctx=>'R$ '+ctx.raw.toLocaleString('pt-BR',{{minimumFractionDigits:2}})}}}}
      }},
      scales:{{
        x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:10}}}},
        y:{{grid:{{color:'rgba(51,65,85,.4)'}}, ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}}
      }}
    }}
  }});
}}
</script>
</body>
</html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Vertical Rio Dashboard — {agora} ===\n")

    print("[ 1/5 ] Meta Ads — período 7d...")
    d7 = buscar_meta_periodo("last_7d")
    print(f"       Gasto R${d7['gasto']:,.2f} | {d7['impressoes']:,} impressões | CTR {d7['ctr']}%")

    print("[ 2/5 ] Meta Ads — períodos 14d e 30d...")
    d14 = buscar_meta_periodo("last_14d")
    d30 = buscar_meta_periodo("last_30d")
    print(f"       14d: R${d14['gasto']:,.2f} | 30d: R${d30['gasto']:,.2f}")

    print("[ 3/5 ] Meta Ads — campanhas e dados diários...")
    campanhas = buscar_meta_campanhas("last_30d")
    diario    = buscar_meta_diario(30)
    print(f"       {len(campanhas)} campanhas | {len(diario)} dias com dados")

    print("[ 4/5 ] Rezdy — buscando reservas...")
    reservas = buscar_rezdy_reservas(500)
    print(f"       {len(reservas)} reservas recuperadas")

    print("[ 5/5 ] Processando e gerando HTML...")
    rezdy_dados = processar_rezdy(reservas, dias=30)
    print(f"       {rezdy_dados['confirmadas']} confirmadas | R${rezdy_dados['receita']:,.2f} receita (30d)")

    meta = {"d7": d7, "d14": d14, "d30": d30, "campanhas": campanhas, "diario": diario}
    html = gerar_html(meta, rezdy_dados, agora)

    with open(ARQUIVO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nOK: {ARQUIVO_HTML} gerado ({len(html):,} chars)")
    print(f"  Resumo: {rezdy_dados['total']} reservas | {rezdy_dados['confirmadas']} confirmadas | {rezdy_dados['taxa_conv']}% conversão")
    print(f"  Meta: R${d30['gasto']:,.2f} gasto | CTR {d30['ctr']}% | CPC R${d30['cpc']:.2f}\n")


if __name__ == "__main__":
    main()
