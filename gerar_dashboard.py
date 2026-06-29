#!/usr/bin/env python3
"""
gerar_dashboard.py — Vertical Rio Marketing Dashboard
Busca dados ao vivo de Meta Ads e Rezdy e gera index.html.
Execute: python gerar_dashboard.py

Credenciais: defina META_TOKEN e REZDY_KEY no arquivo .env
             (mesmo diretório) ou como variáveis de ambiente.
             Exemplo de .env:  META_TOKEN=EAASW...
"""

import json
import os
import pathlib
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ─── Carrega .env se existir ──────────────────────────────────────────────────
def _load_env():
    env_path = pathlib.Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_env()

# ─── Credenciais ──────────────────────────────────────────────────────────────
_FB_TOKEN_FALLBACK = (
    "EAASW2NZCdwiwBRjZBpgb4Unpo2rqHB8iSJfZAt3BkkHB3pxrkevSo0UYx5RnF5hN7dn"
    "ZCUV5yqwuPtfVUqhE3gAyOcfbLvYVhmMb5Cq1OAZBtJQ9cCRQAIce6wU7QNiX1iy11K"
    "H8tELm38U8HKTZCIgriWrUZBUdP4l60xZB4zxDgJVyZAC2bllLHsyDHnos83noLfm9SX"
    "14s0ZCmAP0iLTZBAw5OShUTb84yf4AgQCz201"
)
META_TOKEN   = os.environ.get("META_TOKEN",   _FB_TOKEN_FALLBACK)
META_ACCOUNT = os.environ.get("META_ACCOUNT", "act_2613909812239242")
META_BASE    = "https://graph.facebook.com/v19.0"
REZDY_KEY    = os.environ.get("REZDY_KEY",    "dc7f8d97256e484b8763a983ded2ba22")
REZDY_BASE   = "https://api.rezdy.com/v1"
ARQUIVO_HTML = "index.html"

# ─── HTTP com retry exponencial ───────────────────────────────────────────────
def _req(url, params=None, timeout=20, retries=3):
    """GET com retry exponencial — 1s, 2s, 4s entre tentativas."""
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"       [retry {attempt+1}/{retries-1}] {type(e).__name__} — aguardando {wait}s...")
                time.sleep(wait)
            else:
                raise


# ─── Meta Ads ─────────────────────────────────────────────────────────────────
def meta_get(endpoint, params=None):
    p = {"access_token": META_TOKEN, **(params or {})}
    r = _req(f"{META_BASE}/{endpoint}", params=p, timeout=20)
    return r.json()


def _paginar(resp):
    dados = list(resp.get("data", []))
    while resp.get("paging", {}).get("next"):
        resp = _req(resp["paging"]["next"], timeout=20).json()
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


# ─── Meta Orgânico ────────────────────────────────────────────────────────────
def buscar_paginas():
    """Auto-descobre páginas do Facebook e conta Instagram vinculada ao token."""
    try:
        resp = meta_get("me/accounts", {"fields": "id,name,access_token,instagram_business_account"})
        return resp.get("data", [])
    except Exception as e:
        print(f"       AVISO buscar_paginas: {e}")
        return []


def buscar_organico_facebook(page_id, page_token, dias=90):
    """Busca posts orgânicos da Page Facebook com insights e reações.
    Não usa o parâmetro 'since' (deprecado na v3.3+); filtra por data em Python."""
    hoje  = datetime.now()
    corte = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
    resp  = requests.get(f"{META_BASE}/{page_id}/posts", params={
        "access_token": page_token,
        "fields": "id,message,story,created_time",
        "limit": 100,
    }, timeout=20)
    resp.raise_for_status()

    # Pagina até encontrar posts mais antigos que o corte
    todos = []
    data  = resp.json()
    while True:
        lote = data.get("data", [])
        for p in lote:
            if (p.get("created_time", "")[:10]) >= corte:
                todos.append(p)
        # Para se o último post do lote é mais antigo que o corte
        if not lote or lote[-1].get("created_time", "")[:10] < corte:
            break
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        data = requests.get(next_url, timeout=20).json()
    posts = todos

    resultado = []
    for post in posts:
        pid = post.get("id", "")
        try:
            ins_r = requests.get(f"{META_BASE}/{pid}/insights", params={
                "access_token": page_token,
                "metric": "post_impressions,post_reach,post_engaged_users,post_clicks",
            }, timeout=15).json()
            insights = {}
            for item in ins_r.get("data", []):
                vals = item.get("values") or [{}]
                insights[item["name"]] = int(vals[-1].get("value", 0) or 0)
        except Exception:
            insights = {}
        try:
            reacts_r = requests.get(f"{META_BASE}/{pid}", params={
                "access_token": page_token,
                "fields": "reactions.summary(true),comments.summary(true),shares",
            }, timeout=15).json()
            curtidas        = reacts_r.get("reactions", {}).get("summary", {}).get("total_count", 0)
            comentarios     = reacts_r.get("comments", {}).get("summary", {}).get("total_count", 0)
            compartilhamentos = reacts_r.get("shares", {}).get("count", 0) if reacts_r.get("shares") else 0
        except Exception:
            curtidas = comentarios = compartilhamentos = 0

        resultado.append({
            "id":                pid,
            "tipo":              post.get("type", "status"),
            "plataforma":        "facebook",
            "mensagem":          (post.get("message") or post.get("story") or "")[:180],
            "criado_em":         post.get("created_time", "")[:10],
            "impressoes":        insights.get("post_impressions", 0),
            "alcance":           insights.get("post_reach", 0),
            "engajados":         insights.get("post_engaged_users", 0),
            "cliques":           insights.get("post_clicks", 0),
            "curtidas":          int(curtidas or 0),
            "comentarios":       int(comentarios or 0),
            "compartilhamentos": int(compartilhamentos or 0),
            "salvos":            0,
            "video_views":       0,
        })
    return resultado


def buscar_organico_instagram(ig_id, dias=90):
    """Busca posts orgânicos do Instagram Business Account.
    Usa apenas campos básicos (sem insights.metric) para evitar erro de permissão.
    Filtra por data em Python, sem o parâmetro 'since' (deprecado)."""
    corte = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    resp  = requests.get(f"{META_BASE}/{ig_id}/media", params={
        "access_token": META_TOKEN,
        "fields": "id,caption,media_type,timestamp,like_count,comments_count",
        "limit": 50,
    }, timeout=20)
    resp.raise_for_status()

    todos = []
    data  = resp.json()
    while True:
        lote = data.get("data", [])
        for p in lote:
            if (p.get("timestamp", "")[:10]) >= corte:
                todos.append(p)
        if not lote or lote[-1].get("timestamp", "")[:10] < corte:
            break
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break
        data = requests.get(next_url, timeout=20).json()

    resultado = []
    for post in todos:
        resultado.append({
            "id":                post.get("id", ""),
            "tipo":              post.get("media_type", "IMAGE").lower(),
            "plataforma":        "instagram",
            "mensagem":          (post.get("caption") or "")[:180],
            "criado_em":         post.get("timestamp", "")[:10],
            "impressoes":        0,
            "alcance":           0,
            "curtidas":          int(post.get("like_count", 0) or 0),
            "comentarios":       int(post.get("comments_count", 0) or 0),
            "salvos":            0,
            "video_views":       0,
            "engajados":         0,
            "cliques":           0,
            "compartilhamentos": 0,
        })
    return resultado


# ─── Rezdy ────────────────────────────────────────────────────────────────────
def buscar_rezdy_reservas(limite_total=5000, date_start="2019-01-01"):
    todas, offset = [], 0
    while offset < limite_total:
        params = {"apiKey": REZDY_KEY, "limit": 100, "offset": offset}
        if date_start:
            params["orderDateStart"] = date_start
        resp = _req(f"{REZDY_BASE}/bookings", params=params, timeout=30)
        lote = resp.json().get("bookings", [])
        if not lote:
            break
        todas.extend(lote)
        if len(lote) < 100:
            break
        offset += 100
        time.sleep(0.1)
    return todas


def processar_rezdy(reservas, dias=None):
    hoje      = datetime.now()
    hoje_str  = hoje.strftime("%Y-%m-%d")
    if dias is None:
        recentes = reservas
    else:
        corte    = (hoje - timedelta(days=dias)).strftime("%Y-%m-%d")
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

    datas_com_dados = [d for d in por_dia.keys() if d]
    data_inicio = min(datas_com_dados) if datas_com_dados else (hoje - timedelta(days=89)).strftime("%Y-%m-%d")

    todos_dias = []
    cur = datetime.strptime(data_inicio, "%Y-%m-%d")
    while cur <= hoje:
        d_str = cur.strftime("%Y-%m-%d")
        v = por_dia[d_str]
        todos_dias.append({
            "data":        d_str,
            "confirmadas": v["confirmadas"],
            "abandonadas": v["abandonadas"],
            "outras":      v["outras"],
            "receita":     round(v["receita"], 2),
        })
        cur += timedelta(days=1)

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

    # Todos os bookings do período (compacto para JS) — apenas CONFIRMED
    todos_bookings = []
    for b in sorted(recentes, key=lambda x: x.get("dateCreated", ""), reverse=True):
        if b.get("status") != "CONFIRMED":
            continue
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
            "fonte":   (b.get("source") or "ONLINE").upper(),
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

    # ── Status por cupom: confirmados + abandonados + cancelados ──────────────
    cupom_status = defaultdict(lambda: {"CONFIRMED": 0, "ABANDONED_CART": 0, "CANCELLED": 0, "outros": 0})
    for b in recentes:
        coupon = (b.get("coupon") or "").strip().upper()
        if not coupon:
            continue
        status = b.get("status", "")
        if status == "CONFIRMED":
            cupom_status[coupon]["CONFIRMED"] += 1
        elif status == "ABANDONED_CART":
            cupom_status[coupon]["ABANDONED_CART"] += 1
        elif status == "CANCELLED":
            cupom_status[coupon]["CANCELLED"] += 1
        else:
            cupom_status[coupon]["outros"] += 1

    cupom_status_lista = sorted(
        [{"cupom": k,
          "conf":   v["CONFIRMED"],
          "aband":  v["ABANDONED_CART"],
          "canc":   v["CANCELLED"],
          "outros": v["outros"],
          "total":  v["CONFIRMED"] + v["ABANDONED_CART"] + v["CANCELLED"] + v["outros"]}
         for k, v in cupom_status.items()],
        key=lambda x: x["total"], reverse=True,
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
        "voos_cupom":      voos_cupom,
        "cupom_resumo":    cupom_resumo_lista,
        "cupom_status":    cupom_status_lista,
    }


# ─── HTML ─────────────────────────────────────────────────────────────────────
def gerar_html(meta, rezdy_dados, camps_diario, criativos, atualizado_em, organico_fb=None, organico_ig=None):
    d30 = meta["d30"]
    rz  = rezdy_dados

    # Remove campos pesados de rezdy_json (embutidos separado)
    _excluir = ("todos_bookings", "heatmap", "voos_cupom", "cupom_resumo", "cupom_status")
    rz_slim = {k: v for k, v in rz.items() if k not in _excluir}
    meta_json         = json.dumps(meta,                   ensure_ascii=False)
    rezdy_json        = json.dumps(rz_slim,                ensure_ascii=False)
    camps_diario_json = json.dumps(camps_diario,           ensure_ascii=False)
    bookings_json     = json.dumps(rz["todos_bookings"],   ensure_ascii=False)
    heatmap_json      = json.dumps(rz["heatmap"],          ensure_ascii=False)
    criativos_json    = json.dumps(criativos if isinstance(criativos, dict) else {"d7": criativos, "d14": criativos, "d30": criativos, "d90": criativos}, ensure_ascii=False)
    organico_lista    = (organico_fb or []) + (organico_ig or [])
    organico_json     = json.dumps(organico_lista,         ensure_ascii=False)
    org_tem_dados     = bool(organico_lista)
    voos_cupom_json   = json.dumps(rz["voos_cupom"],       ensure_ascii=False)
    cupom_resumo_json = json.dumps(rz["cupom_resumo"],     ensure_ascii=False)
    cupom_status_json = json.dumps(rz["cupom_status"],     ensure_ascii=False)

    hoje_str   = datetime.now().strftime("%Y-%m-%d")
    d30_str    = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
    d90_str    = rz["por_dia"][0]["data"] if rz["por_dia"] else (datetime.now() - timedelta(days=89)).strftime("%Y-%m-%d")

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
  /* Delta indicators */
  .delta-up {{ color:var(--green) !important; }}
  .delta-dn {{ color:var(--red)   !important; }}
  .kpi-delta[data-delta] {{ font-size:.72rem; margin-top:4px; }}
  /* Heatmap tooltip */
  #heatmap-container td[title] {{ cursor:default; }}
  /* Anomalia badge */
  .badge-anomalia {{ background:rgba(239,68,68,.18); color:#fca5a5; animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.6}} }}
  /* Mobile */
  @media(max-width:640px){{
    main {{ padding-left:10px!important; padding-right:10px!important; }}
    header .max-w-screen-xl {{ padding-left:12px; padding-right:12px; }}
    .kpi-val {{ font-size:1.25rem!important; }}
    .tab-btn {{ padding:6px 11px; font-size:.78rem; }}
    .date-range-wrap {{ min-width:160px; }}
    th,td {{ padding:6px 8px; font-size:.74rem; }}
    .card {{ padding:14px; }}
    canvas {{ max-height:220px; }}
  }}
  @media(max-width:480px){{
    .flex.flex-wrap.items-center.justify-between {{ flex-direction:column; align-items:flex-start; }}
  }}
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
      <button class="tab-btn" onclick="switchTab('organico',this)">Meta Orgânico</button>
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
    <div class="card"><div class="kpi-label">Gasto</div><div class="kpi-val" id="vg-gasto" style="color:var(--indigo)">{fmt_brl(d30["gasto"])}</div><div class="kpi-delta" id="vg-gasto-delta"></div></div>
    <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="vg-impr">{fmt_n(d30["impressoes"])}</div><div class="kpi-delta" id="vg-impr-delta"></div></div>
    <div class="card"><div class="kpi-label">CTR</div><div class="kpi-val" id="vg-ctr" style="color:var(--cyan)">{fmt_pct(d30["ctr"])}</div><div class="kpi-delta" id="vg-ctr-delta"></div></div>
    <div class="card"><div class="kpi-label">CPC Médio</div><div class="kpi-val" id="vg-cpc">{fmt_brl(d30["cpc"])}</div><div class="kpi-delta" id="vg-cpc-delta"></div></div>
  </div>

  <div class="mb-2" style="font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em">Rezdy</div>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
    <div class="card"><div class="kpi-label">Receita Confirmada</div><div class="kpi-val" id="vg-receita" style="color:var(--green)">{fmt_brl(rz["receita"])}</div><div class="kpi-delta" id="vg-receita-delta"></div></div>
    <div class="card"><div class="kpi-label">Confirmadas</div><div class="kpi-val" id="vg-conf">{rz["confirmadas"]}</div><div class="kpi-delta" id="vg-conf-sub">{rz["total"]} total ({fmt_pct(rz["taxa_conv"])} conv.)</div></div>
    <div class="card"><div class="kpi-label">Ticket Médio</div><div class="kpi-val" id="vg-ticket">{fmt_brl(rz["ticket_medio"])}</div><div class="kpi-delta" id="vg-ticket-delta"></div></div>
    <div class="card"><div class="kpi-label">CPA (Gasto÷Conf.)</div><div class="kpi-val" id="vg-cpa" style="color:var(--amber)">—</div><div class="kpi-delta" id="vg-cpa-delta"></div></div>
  </div>

  <!-- Charts row 1 -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Gasto & Cliques Diários</div><canvas id="chartMetaDiario" height="200"></canvas></div>
    <div class="card"><div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Bookings Dia &amp; Fulfilments Dia</div><canvas id="chartRezdyDiario" height="200"></canvas></div>
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

  <div class="grid grid-cols-2 gap-3 mb-5" id="meta-kpis-cards">
    <div class="card"><div class="kpi-label">Gasto</div><div class="kpi-val" id="mk-gasto" style="color:var(--indigo)">{fmt_brl(d30["gasto"])}</div><div class="kpi-delta" id="mk-gasto-delta"></div></div>
    <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="mk-impr">{fmt_n(d30["impressoes"])}</div><div class="kpi-delta" id="mk-impr-delta"></div></div>
    <div class="card"><div class="kpi-label">Cliques</div><div class="kpi-val" id="mk-click">{fmt_n(d30["cliques"])}</div><div class="kpi-delta" id="mk-click-delta"></div></div>
    <div class="card"><div class="kpi-label">CTR</div><div class="kpi-val" id="mk-ctr" style="color:var(--cyan)">{fmt_pct(d30["ctr"])}</div><div class="kpi-delta" id="mk-ctr-delta"></div></div>
    <div class="card"><div class="kpi-label">CPC</div><div class="kpi-val" id="mk-cpc">{fmt_brl(d30["cpc"])}</div><div class="kpi-delta" id="mk-cpc-delta"></div></div>
    <div class="card"><div class="kpi-label">CPM</div><div class="kpi-val" id="mk-cpm">{fmt_brl(d30["cpm"])}</div><div class="kpi-delta" id="mk-cpm-delta"></div></div>
    <div class="card"><div class="kpi-label">Conv. Iniciadas</div><div class="kpi-val" id="mk-conv" style="color:var(--green)">{fmt_n(d30["conversas"])}</div><div class="kpi-delta" id="mk-conv-delta"></div></div>
    <div class="card"><div class="kpi-label">Conexões Msg</div><div class="kpi-val" id="mk-conx" style="color:var(--sub)">{fmt_n(d30["conexoes"])}</div><div class="kpi-delta" id="mk-conx-delta"></div></div>
  </div>

  <!-- Gráfico diário + Campanhas lado a lado -->
  <div class="grid grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Gasto & Cliques Diários</div>
      <canvas id="chartMetaDiario2" height="260"></canvas>
    </div>
    <div class="card">
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem" id="camps-title">Campanhas</div>
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
  </div><!-- /grid gráfico+campanhas -->

  <!-- Criativos -->
  <div class="card mt-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem" id="criativos-title">🎨 Criativos</div>
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

  <div class="grid grid-cols-2 gap-3 mb-5">
    <div class="card"><div class="kpi-label">Total Reservas</div><div class="kpi-val" id="rk-total">{rz["total"]}</div><div class="kpi-delta" id="rk-total-delta"></div></div>
    <div class="card"><div class="kpi-label">Confirmadas</div><div class="kpi-val" id="rk-conf" style="color:var(--green)">{rz["confirmadas"]}</div><div class="kpi-delta" id="rk-conf-delta"></div></div>
    <div class="card"><div class="kpi-label">Voos Realizados</div><div class="kpi-val" id="rk-fulfilments" style="color:var(--cyan)">{rz["fulfilments"]}</div><div class="kpi-delta">pelo dia do voo</div></div>
    <div class="card"><div class="kpi-label">Abandonadas</div><div class="kpi-val" id="rk-aband" style="color:var(--red)">{rz["abandonadas"]}</div><div class="kpi-delta" id="rk-aband-delta"></div></div>
    <div class="card"><div class="kpi-label">Receita</div><div class="kpi-val" id="rk-receita" style="color:var(--green);font-size:1.2rem">{fmt_brl(rz["receita"])}</div><div class="kpi-delta" id="rk-receita-delta"></div></div>
    <div class="card"><div class="kpi-label">Ticket Médio</div><div class="kpi-val" id="rk-ticket" style="font-size:1.3rem">{fmt_brl(rz["ticket_medio"])}</div><div class="kpi-delta" id="rk-ticket-delta"></div></div>
    <div class="card"><div class="kpi-label">Taxa Conversão</div><div class="kpi-val" id="rk-taxa" style="color:var(--cyan)">{fmt_pct(rz["taxa_conv"])}</div><div class="kpi-delta" id="rk-taxa-delta"></div></div>
    <div class="card"><div class="kpi-label">Projeção Mensal</div><div class="kpi-val" id="rk-proj" style="color:var(--amber);font-size:1.2rem">—</div><div class="kpi-delta" id="rk-proj-sub">confirmações estimadas</div></div>
  </div>

  <!-- Receita Histórica — imune ao filtro de datas -->
  <div class="card mb-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div>
        <div style="font-weight:600;font-size:.9rem">Receita Confirmada — Histórico Mensal (todos os anos)</div>
        <div style="font-size:.72rem;color:var(--sub);margin-top:2px">Baseado em todas as reservas · não muda com o filtro de datas</div>
      </div>
      <div style="display:flex;gap:6px" id="hist-year-toggles"></div>
    </div>
    <canvas id="chartReceitaHistorico" height="160"></canvas>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem">Bookings Dia &amp; Fulfilments Dia</div>
        <div style="display:flex;gap:4px">
          <button onclick="setRezdyView('dia')"    class="tab-btn active rezdy-view-btn rezdy-view-btn-dia"    style="padding:3px 10px;font-size:.72rem">Dia</button>
          <button onclick="setRezdyView('semana')" class="tab-btn rezdy-view-btn rezdy-view-btn-semana" style="padding:3px 10px;font-size:.72rem">Semana</button>
          <button onclick="setRezdyView('mes')"    class="tab-btn rezdy-view-btn rezdy-view-btn-mes"    style="padding:3px 10px;font-size:.72rem">Mês</button>
        </div>
      </div>
      <canvas id="chartRezdyDiario2" height="200"></canvas>
    </div>
    <div class="card">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem">Receita Diária Confirmada</div>
        <div style="display:flex;gap:4px">
          <button onclick="setRezdyView('dia')"    class="tab-btn active rezdy-view-btn rezdy-view-btn-dia"    style="padding:3px 10px;font-size:.72rem">Dia</button>
          <button onclick="setRezdyView('semana')" class="tab-btn rezdy-view-btn rezdy-view-btn-semana" style="padding:3px 10px;font-size:.72rem">Semana</button>
          <button onclick="setRezdyView('mes')"    class="tab-btn rezdy-view-btn rezdy-view-btn-mes"    style="padding:3px 10px;font-size:.72rem">Mês</button>
        </div>
      </div>
      <canvas id="chartRezdyReceita" height="200"></canvas>
    </div>
  </div>

  <!-- Bookings por Fonte + Booking vs Fulfilment lado a lado -->
  <div class="grid grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem">Bookings: Online vs Interno vs Outros</div>
        <div style="display:flex;gap:6px">
          <button onclick="setFonteView('dia')"   id="fonte-btn-dia"    class="tab-btn active" style="padding:4px 12px;font-size:.75rem">Dia</button>
          <button onclick="setFonteView('semana')" id="fonte-btn-semana" class="tab-btn"         style="padding:4px 12px;font-size:.75rem">Semana</button>
          <button onclick="setFonteView('mes')"    id="fonte-btn-mes"    class="tab-btn"         style="padding:4px 12px;font-size:.75rem">Mês</button>
        </div>
      </div>
      <canvas id="chartBookingsFonte" height="200"></canvas>
    </div>
    <div class="card">
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem">Dia da Reserva vs Dia do Voo</div>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
          <span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
            <span style="display:inline-block;width:12px;height:12px;background:rgba(99,102,241,.65);border-radius:2px"></span>Reservas feitas
          </span>
          <span style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">
            <span style="display:inline-block;width:22px;height:2px;background:#06b6d4;border-radius:2px"></span>Voos realizados
          </span>
          <div style="display:flex;gap:4px">
            <button onclick="setFulfilView('dia')"    id="fulfil-btn-dia"    class="tab-btn active" style="padding:3px 10px;font-size:.72rem">Dia</button>
            <button onclick="setFulfilView('semana')" id="fulfil-btn-semana" class="tab-btn"        style="padding:3px 10px;font-size:.72rem">Semana</button>
            <button onclick="setFulfilView('mes')"    id="fulfil-btn-mes"    class="tab-btn"        style="padding:3px 10px;font-size:.72rem">Mês</button>
          </div>
        </div>
      </div>
      <canvas id="chartBookingVsFulfilment" height="200"></canvas>
    </div>
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
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div class="flex items-center gap-3">
        <div style="font-weight:600;font-size:.9rem">Voos Confirmados via Cupom</div>
        <span class="badge badge-blue" id="cupom-count">—</span>
      </div>
      <button id="cupom-section-toggle" onclick="toggleCard('cupom-section-body','cupom-section-toggle')" style="background:var(--surface2);border:1px solid var(--border);color:var(--sub);border-radius:6px;padding:4px 12px;font-size:.75rem;cursor:pointer">▲ Minimizar</button>
    </div>

    <div id="cupom-section-body">
    <div id="cupom-vazio" style="display:none;color:#94a3b8;font-size:.85rem;padding:8px 0">
      Nenhum voo confirmado com cupom no período selecionado.
    </div>

    <div id="cupom-tabelas">
      <div style="font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Status por cupom</div>
      <div style="overflow-x:auto;margin-bottom:20px">
        <table>
          <thead><tr>
            <th>Cupom</th>
            <th style="text-align:right">✅ Confirmados</th>
            <th style="text-align:right">❌ Abandonados</th>
            <th style="text-align:right">🚫 Cancelados</th>
            <th style="text-align:right">Total</th>
            <th style="text-align:right">Taxa Conv.</th>
          </tr></thead>
          <tbody id="cupom-status-body"></tbody>
        </table>
      </div>

      <div style="font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Resumo por cupom (confirmados)</div>
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
      <div style="display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin-bottom:12px">
        <select id="cupom-detail-filter-fonte" onchange="renderCupons(currentFrom, currentTo)" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem">
          <option value="">Todas as fontes</option>
          <option value="ONLINE">Online</option>
          <option value="INTERNAL">Interno</option>
        </select>
        <!-- Multi-select pills de cupons -->
        <div style="display:flex;flex-direction:column;gap:6px;flex:1;min-width:240px">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span style="font-size:.75rem;color:#94a3b8;white-space:nowrap">Selecionar cupons:</span>
            <div id="cupom-pills" style="display:flex;flex-wrap:wrap;gap:5px"></div>
            <button onclick="clearCupomSel()" id="cupom-clear-btn" style="display:none;background:var(--surface2);border:1px solid var(--border);color:var(--sub);border-radius:6px;padding:3px 10px;font-size:.73rem;cursor:pointer">✕ Limpar</button>
          </div>
          <div id="cupom-all-pills" style="display:flex;flex-wrap:wrap;gap:5px"></div>
        </div>
      </div>

      <!-- Painel de comparação (aparece quando 2+ cupons selecionados) -->
      <div id="cupom-comparar" style="display:none;margin-bottom:20px">
        <div style="font-size:.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">⚖️ Comparação entre cupons selecionados</div>
        <div style="overflow-x:auto;margin-bottom:14px">
          <table id="cupom-comparar-table">
            <thead><tr id="cupom-comparar-head"></tr></thead>
            <tbody id="cupom-comparar-body"></tbody>
          </table>
        </div>
        <canvas id="chartCupomComparacao" height="120"></canvas>
      </div>

      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Nº Pedido</th><th>Cupom</th><th>Produto</th>
            <th style="text-align:right">Pax</th>
            <th style="text-align:right">Valor</th>
            <th>Reservado</th><th>Voo</th><th>Fonte</th><th>Cliente</th>
          </tr></thead>
          <tbody id="cupom-detail-body"></tbody>
        </table>
      </div>
    </div>
    </div><!-- /cupom-section-body -->
  </div>

  <!-- ── Últimas Reservas ────────────────────────────────────────────────── -->
  <div class="card">
    <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">Últimas Reservas <span class="badge badge-gray" id="book-count"></span></div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input type="search" id="book-search" placeholder="🔍 Buscar nº ou produto…" oninput="debounce(()=>renderBookings(currentFrom,currentTo),250)()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem;width:180px;outline:none">
        <select id="book-filter-status" onchange="renderBookings(currentFrom, currentTo)" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem">
          <option value="CONFIRMED" selected>Confirmados</option>
        </select>
        <button onclick="exportCSV()" title="Exportar CSV" style="background:var(--surface2);border:1px solid var(--border);color:var(--sub);border-radius:6px;padding:4px 12px;font-size:.75rem;cursor:pointer">⬇ CSV</button>
        <button id="book-section-toggle" onclick="toggleCard('book-section-body','book-section-toggle')" style="background:var(--surface2);border:1px solid var(--border);color:var(--sub);border-radius:6px;padding:4px 12px;font-size:.75rem;cursor:pointer">▲ Minimizar</button>
      </div>
    </div>
    <div id="book-section-body" style="overflow-x:auto">
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


<!-- ══════════════════════════ META ORGÂNICO ═══════════════════════════════ -->
<div id="tab-organico" class="tab-content pt-3" style="display:none">

  <!-- Estado: sem dados -->
  <div id="org-sem-dados" style="display:{'none' if org_tem_dados else 'block'}">
    <div class="card" style="text-align:center;padding:48px 24px">
      <div style="font-size:2.5rem;margin-bottom:14px">📊</div>
      <div style="font-weight:700;font-size:1.1rem;margin-bottom:8px">Dados orgânicos não disponíveis</div>
      <div style="color:var(--sub);font-size:.85rem;max-width:480px;margin:0 auto">
        O token atual não retornou permissão de Page ou Instagram Business Account.<br>
        Garanta as permissões <code>pages_read_engagement</code> e <code>instagram_manage_insights</code> no token Meta.
      </div>
    </div>
  </div>

  <!-- Estado: com dados -->
  <div id="org-com-dados" style="display:{'block' if org_tem_dados else 'none'}">

    <!-- KPIs Facebook -->
    <div class="mb-2 mt-1" style="font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em">Facebook Orgânico</div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div class="card"><div class="kpi-label">Posts</div><div class="kpi-val" id="org-fb-posts" style="color:#1877f2">—</div></div>
      <div class="card"><div class="kpi-label">Alcance Total</div><div class="kpi-val" id="org-fb-alcance">—</div></div>
      <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="org-fb-impr">—</div></div>
      <div class="card"><div class="kpi-label">Eng. Médio/Post</div><div class="kpi-val" id="org-fb-eng" style="color:var(--cyan)">—</div></div>
    </div>

    <!-- KPIs Instagram -->
    <div class="mb-2" style="font-size:.7rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em">Instagram Orgânico</div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
      <div class="card"><div class="kpi-label">Posts</div><div class="kpi-val" id="org-ig-posts" style="color:#e1306c">—</div></div>
      <div class="card"><div class="kpi-label">Alcance Total</div><div class="kpi-val" id="org-ig-alcance">—</div></div>
      <div class="card"><div class="kpi-label">Impressões</div><div class="kpi-val" id="org-ig-impr">—</div></div>
      <div class="card"><div class="kpi-label">Eng. Médio/Post</div><div class="kpi-val" id="org-ig-eng" style="color:var(--cyan)">—</div></div>
    </div>

    <!-- Charts row 1 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <div class="card">
        <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">FB vs IG — Médias por Plataforma</div>
        <canvas id="chartOrgComparativo" height="220"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Posts por Semana</div>
        <canvas id="chartOrgTimeline" height="220"></canvas>
      </div>
    </div>

    <!-- Charts row 2 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
      <div class="card">
        <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Engajamento Médio por Tipo de Post</div>
        <canvas id="chartOrgTipos" height="220"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">Alcance Semanal — FB vs IG</div>
        <canvas id="chartOrgAlcance" height="220"></canvas>
      </div>
    </div>

    <!-- Tabela de posts -->
    <div class="card">
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div style="font-weight:600;font-size:.9rem">Todos os Posts Orgânicos</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <select id="org-filter-plataforma" onchange="renderOrganicoPosts()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem">
            <option value="">Todas as plataformas</option>
            <option value="facebook">Facebook</option>
            <option value="instagram">Instagram</option>
          </select>
          <select id="org-filter-tipo" onchange="renderOrganicoPosts()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem">
            <option value="">Todos os tipos</option>
          </select>
          <select id="org-sort" onchange="renderOrganicoPosts()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:5px 10px;font-size:.8rem">
            <option value="alcance">Por Alcance</option>
            <option value="impressoes">Por Impressões</option>
            <option value="curtidas">Por Curtidas</option>
            <option value="comentarios">Por Comentários</option>
            <option value="criado_em">Por Data</option>
          </select>
        </div>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Plat.</th>
            <th>Tipo</th>
            <th>Data</th>
            <th>Post</th>
            <th style="text-align:right">Alcance</th>
            <th style="text-align:right">Impressões</th>
            <th style="text-align:right">Curtidas</th>
            <th style="text-align:right">Coment.</th>
            <th style="text-align:right">Salvos/Comp.</th>
            <th style="text-align:right">Total Eng.</th>
          </tr></thead>
          <tbody id="org-posts-body"></tbody>
        </table>
      </div>
    </div>

  </div><!-- /org-com-dados -->

</div><!-- /tab-organico -->


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
const CRIATIVOS_PERIODOS = {criativos_json};
const VOOS_CUPOM   = {voos_cupom_json};
const ORGANICO     = {organico_json};
const CUPOM_STATUS = {cupom_status_json};
const HOJE         = "{hoje_str}";
const D30_FROM     = "{d30_str}";
const D90_FROM     = "{d90_str}";
let currentFrom = D30_FROM, currentTo = HOJE;

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fBRL = v => 'R$ ' + Number(v).toLocaleString('pt-BR',{{minimumFractionDigits:2,maximumFractionDigits:2}});
const fN   = v => Math.round(v).toLocaleString('pt-BR');
const fPct = v => Number(v).toFixed(2) + '%';
const fDate = d => d && d.length >= 10 ? d.slice(8)+'-'+d.slice(5,7)+'-'+d.slice(0,4) : (d||'—');
const fAxis = d => d && d.length >= 10 ? d.slice(8)+'-'+d.slice(5,7) : d;

// XSS-safe: escapa HTML para uso em innerHTML
const escHtml = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// Debounce: evita re-render a cada tecla
function debounce(fn, ms) {{
  let t; return (...args) => {{ clearTimeout(t); t = setTimeout(()=>fn(...args), ms); }};
}}

// Delta KPI: retorna HTML de variação vs período anterior
// goodDir: 1 = ↑ é bom (receita), -1 = ↓ é bom (CPC, CPA)
function fDelta(cur, prev, goodDir=1) {{
  if (!prev || prev === 0) return '';
  const pct = (cur - prev) / prev * 100;
  const up  = pct >= 0;
  const good = goodDir === 1 ? up : !up;
  const color = good ? 'var(--green)' : 'var(--red)';
  const arrow = up ? '↑' : '↓';
  return `<span style="color:${{color}}">${{arrow}} ${{Math.abs(pct).toFixed(1)}}% vs ant.</span>`;
}}

function setText(id, val) {{
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}}

function setHtml(id, val) {{
  const el = document.getElementById(id);
  if (el) el.innerHTML = val;
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
  const labels = mDays.map(d => fAxis(d.data));
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

let _rezdyView = 'dia';
let _rezdyDays = [];

function aggregateRezdyDays(rDays, view) {{
  if (view === 'dia') return rDays;
  const agg = {{}};
  for (const d of rDays) {{
    let key;
    if (view === 'semana') {{
      const dt = new Date(d.data + 'T12:00:00');
      dt.setDate(dt.getDate() - dt.getDay());
      key = dt.toISOString().slice(0,10);
    }} else {{
      key = d.data.slice(0,7);
    }}
    if (!agg[key]) agg[key] = {{data:key, confirmadas:0, abandonadas:0, outras:0, receita:0}};
    agg[key].confirmadas += d.confirmadas;
    agg[key].abandonadas += d.abandonadas;
    agg[key].outras      += (d.outras||0);
    agg[key].receita     += d.receita;
  }}
  return Object.values(agg).sort((a,b)=>a.data.localeCompare(b.data));
}}

function setRezdyView(view) {{
  _rezdyView = view;
  document.querySelectorAll('.rezdy-view-btn').forEach(btn => {{
    const isActive = btn.classList.contains('rezdy-view-btn-' + view);
    btn.classList.toggle('active', isActive);
  }});
  const agg = aggregateRezdyDays(_rezdyDays, view);
  buildRezdyDiario('chartRezdyDiario',  agg);
  buildRezdyDiario('chartRezdyDiario2', agg);
  buildRezdyReceita('chartRezdyReceita', agg);
}}

function buildRezdyDiario(canvasId, rDays) {{
  const labelFmt = d => _rezdyView === 'mes' ? d.data : fAxis(d.data);

  // Fulfilments por bucket (tour date) — usa BOOKINGS global (só CONFIRMED)
  const bucket = date => {{
    if (_rezdyView === 'semana') {{
      const d = new Date(date + 'T12:00:00');
      d.setDate(d.getDate() - d.getDay());
      return d.toISOString().slice(0,10);
    }}
    if (_rezdyView === 'mes') return date.slice(0,7);
    return date;
  }};
  const from = rDays.length ? rDays[0].data : '';
  const to   = rDays.length ? rDays[rDays.length-1].data : '';
  const fulfMap = {{}};
  for (const b of BOOKINGS) {{
    if (b.t && b.t >= from && b.t <= to) {{
      const k = bucket(b.t);
      fulfMap[k] = (fulfMap[k]||0) + 1;
    }}
  }}

  makeChart(canvasId, {{
    type:'bar',
    data:{{
      labels: rDays.map(labelFmt),
      datasets:[
        {{label:'Bookings Dia', data:rDays.map(d=>d.confirmadas), backgroundColor:'rgba(34,197,94,.75)', borderRadius:3, order:2}},
        {{label:'Fulfilments Dia', data:rDays.map(d=>fulfMap[d.data]||0),
          type:'line', borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,.12)',
          fill:true, tension:0.4, pointRadius:2, borderWidth:2, order:1}},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:14}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true,ticks:{{stepSize:1}}}}}}
    }}
  }});
}}

function buildRezdyReceita(canvasId, rDays) {{
  const labelFmt = d => _rezdyView === 'mes' ? d.data : fAxis(d.data);
  makeChart(canvasId, {{
    type:'line',
    data:{{
      labels: rDays.map(labelFmt),
      datasets:[{{label:'Receita Confirmada (R$)', data:rDays.map(d=>d.receita), borderColor:'#22c55e', backgroundColor:'rgba(34,197,94,.1)', fill:true, tension:0.4, pointRadius:2}}]
    }},
    options:{{
      responsive:true,
      plugins:{{legend:{{labels:{{boxWidth:12}}}},tooltip:{{callbacks:{{label:ctx=>fBRL(ctx.raw)}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:14}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},ticks:{{callback:v=>'R$'+v.toLocaleString('pt-BR')}}}}}}
    }}
  }});
}}

let _fulfilView = 'dia';
let _fulfilFrom = '', _fulfilTo = '';

function setFulfilView(view) {{
  _fulfilView = view;
  ['dia','semana','mes'].forEach(v => {{
    const btn = document.getElementById('fulfil-btn-' + v);
    if (btn) btn.classList.toggle('active', v === view);
  }});
  buildBookingVsFulfilment('chartBookingVsFulfilment', _fulfilFrom, _fulfilTo);
}}

function buildBookingVsFulfilment(canvasId, from, to) {{
  _fulfilFrom = from; _fulfilTo = to;

  const bucket = date => {{
    if (_fulfilView === 'dia') return date;
    if (_fulfilView === 'semana') {{
      const d = new Date(date + 'T12:00:00');
      d.setDate(d.getDate() - d.getDay());
      return d.toISOString().slice(0,10);
    }}
    return date.slice(0,7);
  }};

  const dispLabel = k => _fulfilView === 'mes' ? k : fAxis(k);

  const bookMap = {{}};
  const fulfMap = {{}};
  for (const b of BOOKINGS) {{
    if (b.s !== 'CONFIRMED') continue;
    if (b.d >= from && b.d <= to) {{ const k = bucket(b.d); bookMap[k] = (bookMap[k]||0) + 1; }}
    if (b.t && b.t >= from && b.t <= to) {{ const k = bucket(b.t); fulfMap[k] = (fulfMap[k]||0) + 1; }}
  }}

  const keys = [...new Set([...Object.keys(bookMap), ...Object.keys(fulfMap)])].sort();

  makeChart(canvasId, {{
    type: 'bar',
    data: {{
      labels: keys.map(dispLabel),
      datasets: [
        {{ label:'Reservas feitas', data:keys.map(k=>bookMap[k]||0),
           backgroundColor:'rgba(99,102,241,.65)', borderRadius:3, order:2 }},
        {{ label:'Voos realizados (fulfilment)', data:keys.map(k=>fulfMap[k]||0),
           type:'line', borderColor:'#06b6d4', backgroundColor:'rgba(6,182,212,.12)',
           fill:true, tension:0.4, pointRadius:2, borderWidth:2, order:1 }},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}}}},
      scales:{{
        x:{{grid:{{display:false}}, ticks:{{maxTicksLimit:16}}}},
        y:{{grid:{{color:'rgba(51,65,85,.4)'}}, beginAtZero:true, ticks:{{stepSize:1}}}}
      }}
    }}
  }});
}}

// ─── Bookings por Fonte ───────────────────────────────────────────────────────
let _fonteView = 'dia';
let _fonteFrom = '', _fonteTo = '';

function setFonteView(view) {{
  _fonteView = view;
  ['dia','semana','mes'].forEach(v => {{
    const btn = document.getElementById('fonte-btn-' + v);
    if (btn) {{ btn.classList.toggle('active', v === view); }}
  }});
  buildBookingsFonte(_fonteFrom, _fonteTo);
}}

function buildBookingsFonte(from, to) {{
  _fonteFrom = from; _fonteTo = to;
  const bk = BOOKINGS.filter(b => b.d >= from && b.d <= to && b.s === 'CONFIRMED');

  const bucket = (date) => {{
    if (_fonteView === 'dia')   return date;
    if (_fonteView === 'semana') {{
      const d = new Date(date + 'T12:00:00');
      const dow = d.getDay(); // 0=Sun
      d.setDate(d.getDate() - dow);
      return d.toISOString().slice(0,10);
    }}
    return date.slice(0,7);
  }};

  const agg = {{}};
  for (const b of bk) {{
    const k = bucket(b.d);
    if (!agg[k]) agg[k] = {{online:0, interno:0, outros:0}};
    const f = (b.f || '').toUpperCase();
    if (f === 'ONLINE')   agg[k].online++;
    else if (f === 'INTERNAL' || f === 'INTERNO') agg[k].interno++;
    else agg[k].outros++;
  }}

  const labels = Object.keys(agg).sort();
  const dispLabel = l => _fonteView === 'mes' ? l.slice(0,7) : fAxis(l);
  makeChart('chartBookingsFonte', {{
    type: 'bar',
    data: {{
      labels: labels.map(dispLabel),
      datasets: [
        {{ label:'Online',   data:labels.map(l=>agg[l].online),   backgroundColor:'rgba(99,102,241,.75)', borderRadius:3, stack:'s' }},
        {{ label:'Interno',  data:labels.map(l=>agg[l].interno),  backgroundColor:'rgba(34,197,94,.75)',  borderRadius:3, stack:'s' }},
        {{ label:'Outros',   data:labels.map(l=>agg[l].outros),   backgroundColor:'rgba(245,158,11,.6)',  borderRadius:3, stack:'s' }},
      ]
    }},
    options:{{
      responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:16}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true,ticks:{{stepSize:1}}}}}}
    }}
  }});
}}

// ─── Date range apply ─────────────────────────────────────────────────────────
function applyDateRange(from, to) {{
  currentFrom = from; currentTo = to;

  // ── Período atual ──
  const mDays  = META_DATA.diario.filter(d => d.data >= from && d.data <= to);
  const mGasto = mDays.reduce((s,d)=>s+d.gasto,0);
  const mImpr  = mDays.reduce((s,d)=>s+d.impressoes,0);
  const mClick = mDays.reduce((s,d)=>s+d.cliques,0);
  const mConv  = mDays.reduce((s,d)=>s+(d.conversas||0),0);
  const mConx  = mDays.reduce((s,d)=>s+(d.conexoes||0),0);
  const mCtr   = mImpr  ? mClick/mImpr*100  : 0;
  const mCpc   = mClick ? mGasto/mClick     : 0;
  const mCpm   = mImpr  ? mGasto/mImpr*1000 : 0;

  const rDays  = REZDY_DATA.por_dia.filter(d => d.data >= from && d.data <= to);
  const rConf  = rDays.reduce((s,d)=>s+d.confirmadas,0);
  const rAband = rDays.reduce((s,d)=>s+d.abandonadas,0);
  const rOutras= rDays.reduce((s,d)=>s+(d.outras||0),0);
  const rTotal = rConf + rAband + rOutras;
  const rRec   = rDays.reduce((s,d)=>s+d.receita,0);
  const rTick  = rConf ? rRec/rConf : 0;
  const rTaxa  = rTotal ? rConf/rTotal*100 : 0;
  const mCpa   = rConf ? mGasto/rConf : 0;

  // ── Período anterior (mesmo número de dias, imediatamente antes) ──
  const days = Math.round((new Date(to) - new Date(from)) / 86400000) + 1;
  const prevTo   = new Date(from + 'T12:00:00'); prevTo.setDate(prevTo.getDate()-1);
  const prevFrom = new Date(prevTo);             prevFrom.setDate(prevFrom.getDate()-days+1);
  const pFrom = prevFrom.toISOString().slice(0,10);
  const pTo   = prevTo.toISOString().slice(0,10);

  const pmDays  = META_DATA.diario.filter(d => d.data >= pFrom && d.data <= pTo);
  const pmGasto = pmDays.reduce((s,d)=>s+d.gasto,0);
  const pmImpr  = pmDays.reduce((s,d)=>s+d.impressoes,0);
  const pmClick = pmDays.reduce((s,d)=>s+d.cliques,0);
  const pmConv  = pmDays.reduce((s,d)=>s+(d.conversas||0),0);
  const pmCtr   = pmImpr  ? pmClick/pmImpr*100  : 0;
  const pmCpc   = pmClick ? pmGasto/pmClick     : 0;
  const pmCpm   = pmImpr  ? pmGasto/pmImpr*1000 : 0;

  const prDays  = REZDY_DATA.por_dia.filter(d => d.data >= pFrom && d.data <= pTo);
  const prConf  = prDays.reduce((s,d)=>s+d.confirmadas,0);
  const prAband = prDays.reduce((s,d)=>s+d.abandonadas,0);
  const prOutras= prDays.reduce((s,d)=>s+(d.outras||0),0);
  const prTotal = prConf + prAband + prOutras;
  const prRec   = prDays.reduce((s,d)=>s+d.receita,0);
  const prTick  = prConf ? prRec/prConf : 0;
  const prCpa   = prConf ? pmGasto/prConf : 0;

  // ── Projeção mensal ──
  const hoje = new Date(HOJE + 'T12:00:00');
  const daysInMonth  = new Date(hoje.getFullYear(), hoje.getMonth()+1, 0).getDate();
  const dayOfMonth   = hoje.getDate();
  const dailyAvgConf = days > 0 ? rConf / days : 0;
  const projMes      = Math.round(dailyAvgConf * daysInMonth);
  const daysLeft     = daysInMonth - dayOfMonth;

  // ── Anomalias simples ──
  // CTR caiu > 30% vs anterior → avisa
  const ctrAnomalia = pmCtr > 0 && mCtr < pmCtr * 0.7;

  // ── Update Visão Geral KPIs ──
  setText('vg-gasto',  fBRL(mGasto));  setHtml('vg-gasto-delta',  fDelta(mGasto, pmGasto, -1));
  setText('vg-impr',   fN(mImpr));     setHtml('vg-impr-delta',   fDelta(mImpr,  pmImpr,   1));
  setText('vg-ctr',    fPct(mCtr));    setHtml('vg-ctr-delta',    fDelta(mCtr,   pmCtr,    1));
  setText('vg-cpc',    fBRL(mCpc));    setHtml('vg-cpc-delta',    fDelta(mCpc,   pmCpc,   -1));
  setText('vg-receita',fBRL(rRec));    setHtml('vg-receita-delta',fDelta(rRec,   prRec,    1));
  setText('vg-conf',   rConf);
  setText('vg-conf-sub', rTotal + ' total (' + fPct(rTaxa) + ' conv.)');
  setText('vg-ticket', fBRL(rTick));   setHtml('vg-ticket-delta', fDelta(rTick,  prTick,   1));
  setText('vg-cpa',    mCpa ? fBRL(mCpa) : '—'); setHtml('vg-cpa-delta', fDelta(mCpa, prCpa, -1));

  // ── Update Funil ──
  setText('fn-impr',    fN(mImpr));
  setText('fn-click',   fN(mClick));
  setText('fn-ctr-lbl', fPct(mCtr) + ' CTR' + (ctrAnomalia ? ' ⚠' : ''));
  setText('fn-total',   rTotal);
  setText('fn-conf',    rConf);
  setText('fn-taxa-lbl', fPct(rTaxa) + ' taxa');

  // ── Update Meta Ads KPIs ──
  setText('mk-gasto', fBRL(mGasto)); setHtml('mk-gasto-delta', fDelta(mGasto, pmGasto, -1));
  setText('mk-impr',  fN(mImpr));   setHtml('mk-impr-delta',  fDelta(mImpr,  pmImpr,   1));
  setText('mk-click', fN(mClick));  setHtml('mk-click-delta', fDelta(mClick, pmClick,  1));
  setText('mk-ctr',   fPct(mCtr));  setHtml('mk-ctr-delta',   fDelta(mCtr,   pmCtr,    1) + (ctrAnomalia ? ' <span class="badge badge-anomalia">⚠ anomalia</span>' : ''));
  setText('mk-cpc',   fBRL(mCpc));  setHtml('mk-cpc-delta',   fDelta(mCpc,   pmCpc,   -1));
  setText('mk-cpm',   fBRL(mCpm));  setHtml('mk-cpm-delta',   fDelta(mCpm,   pmCpm,   -1));
  setText('mk-conv',  fN(mConv));   setHtml('mk-conv-delta',  fDelta(mConv,  pmConv,   1));
  setText('mk-conx',  fN(mConx));   setHtml('mk-conx-delta',  fDelta(mConx,  0));

  // ── Update Rezdy KPIs ──
  setText('rk-total',  rTotal);    setHtml('rk-total-delta',  fDelta(rTotal, prTotal,  1));
  setText('rk-conf',   rConf);     setHtml('rk-conf-delta',   fDelta(rConf,  prConf,   1));
  setText('rk-aband',  rAband);    setHtml('rk-aband-delta',  fDelta(rAband, prAband, -1));
  setText('rk-receita',fBRL(rRec));setHtml('rk-receita-delta',fDelta(rRec,   prRec,    1));
  setText('rk-ticket', fBRL(rTick));setHtml('rk-ticket-delta',fDelta(rTick,  prTick,   1));
  setText('rk-taxa',   fPct(rTaxa));setHtml('rk-taxa-delta',  fDelta(rTaxa,  prTotal?prConf/prTotal*100:0, 1));
  setText('rk-proj',   fN(projMes));
  setText('rk-proj-sub', `média ${{dailyAvgConf.toFixed(1)}}/dia · mais ${{daysLeft}} dias restantes`);
  const rFulfilments = BOOKINGS.filter(b => b.s === 'CONFIRMED' && b.t && b.t >= from && b.t <= to && b.t <= HOJE).length;
  setText('rk-fulfilments', rFulfilments);

  // ── Update charts ──
  buildMetaDiario('chartMetaDiario', mDays);
  buildMetaDiario('chartMetaDiario2', mDays);
  _rezdyDays = rDays;
  const rDaysAgg = aggregateRezdyDays(rDays, _rezdyView);
  buildRezdyDiario('chartRezdyDiario', rDaysAgg);
  buildRezdyDiario('chartRezdyDiario2', rDaysAgg);
  buildRezdyReceita('chartRezdyReceita', rDaysAgg);
  buildBookingVsFulfilment('chartBookingVsFulfilment', from, to);
  buildBookingsFonte(from, to);

  // ── Tabelas e gráficos dinâmicos ──
  renderCampanhas(from, to);
  renderProdutos(from, to);
  renderBookings(from, to);
  renderPaises(from, to);
  renderCupons(from, to);
  renderOrganico(from, to);

  // ── Range label + títulos dinâmicos ──
  setText('range-label', days + ' dias selecionados');
  const fmtD = d => d.slice(8) + '-' + d.slice(5,7) + '-' + d.slice(0,4);
  setText('camps-title', 'Campanhas — ' + fmtD(from) + ' a ' + fmtD(to));
  renderCriativos(from, to);
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
    const nomeEsc = escHtml(c.nome.slice(0,55));
    return `<tr>
      <td title="${{escHtml(c.nome)}}"><span style="font-size:.65rem;font-weight:700;padding:1px 6px;border-radius:4px;background:${{tc}}22;color:${{tc}};margin-right:6px">${{tipo}}</span><span style="font-weight:500">${{nomeEsc}}</span></td>
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

function renderCriativos(from, to) {{
  const TIPO_COLOR = {{MSG:'#22c55e', CONV:'#6366f1', TRAF:'#06b6d4'}};
  const TIPO_LABEL = {{MSG:'Mensagens', CONV:'Conversão / Carrinho', TRAF:'Tráfego'}};

  // Seleciona o período mais próximo ao range selecionado
  const days = from && to ? Math.round((new Date(to) - new Date(from)) / 86400000) + 1 : 30;
  let periodoKey = 'd90';
  let periodoLabel = 'últ. 90 dias';
  if (days <= 7)  {{ periodoKey = 'd7';  periodoLabel = 'últ. 7 dias';  }}
  else if (days <= 14) {{ periodoKey = 'd14'; periodoLabel = 'últ. 14 dias'; }}
  else if (days <= 30) {{ periodoKey = 'd30'; periodoLabel = 'últ. 30 dias'; }}
  const data = (CRIATIVOS_PERIODOS[periodoKey] || CRIATIVOS_PERIODOS.d30 || []);
  setText('criativos-title', '🎨 Criativos — ' + periodoLabel);

  const grupos = {{MSG:[], CONV:[], TRAF:[]}};
  for (const a of data) {{
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
      const nomeEsc    = escHtml(a.nome);
      html += `<tr data-criativos="${{tipo}}" style="${{hidden ? 'display:none' : ''}}">
        <td style="font-family:monospace;font-size:.7rem;color:#94a3b8;white-space:nowrap">${{escHtml(a.id)}}</td>
        <td style="font-size:.82rem;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${{nomeEsc}}">${{nomeEsc.slice(0,55)}}</td>
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

// ─── Cupons — multi-select e comparação ──────────────────────────────────────
const CUPOM_COLORS = ['#6366f1','#22c55e','#f59e0b','#ef4444','#06b6d4','#a855f7','#f97316','#14b8a6'];
let selectedCupons = new Set();

function toggleCupom(c) {{
  if (selectedCupons.has(c)) selectedCupons.delete(c);
  else selectedCupons.add(c);
  renderCupons(currentFrom, currentTo);
}}

function clearCupomSel() {{
  selectedCupons.clear();
  renderCupons(currentFrom, currentTo);
}}

function _buildPills(cupons) {{
  const allPillsEl  = document.getElementById('cupom-all-pills');
  const selPillsEl  = document.getElementById('cupom-pills');
  const clearBtn    = document.getElementById('cupom-clear-btn');
  if (!allPillsEl) return;

  // Chips clicáveis de todos os cupons do período
  allPillsEl.innerHTML = cupons.map((c, i) => {{
    const sel  = selectedCupons.has(c);
    const col  = CUPOM_COLORS[i % CUPOM_COLORS.length];
    const bg   = sel ? col : 'transparent';
    const border = sel ? col : 'var(--border)';
    const color  = sel ? '#fff' : 'var(--sub)';
    return `<button onclick="toggleCupom('${{c}}')"
      style="background:${{bg}};border:1.5px solid ${{border}};color:${{color}};border-radius:99px;
             padding:3px 12px;font-size:.73rem;font-weight:600;cursor:pointer;transition:all .15s"
      title="${{sel ? 'Remover' : 'Adicionar'}} da comparação">${{c}}</button>`;
  }}).join('');

  // Pills selecionados no topo
  if (selectedCupons.size > 0) {{
    selPillsEl.innerHTML = [...selectedCupons].map((c,i) => {{
      const col = CUPOM_COLORS[cupons.indexOf(c) % CUPOM_COLORS.length];
      return `<span style="background:${{col}};color:#fff;border-radius:99px;padding:2px 10px;font-size:.72rem;font-weight:700">${{c}}</span>`;
    }}).join('');
    if (clearBtn) clearBtn.style.display = 'inline-block';
  }} else {{
    selPillsEl.innerHTML = '';
    if (clearBtn) clearBtn.style.display = 'none';
  }}
}}

function _renderComparacao(cupons, allInPeriod, fonteFilter) {{
  const panel = document.getElementById('cupom-comparar');
  if (!panel) return;
  if (cupons.length < 2) {{ panel.style.display = 'none'; return; }}
  panel.style.display = 'block';

  // Agrega métricas por cupom
  const stats = {{}};
  for (const c of cupons) stats[c] = {{usos:0,receita:0,pax:0,tickets:[]}};
  for (const b of allInPeriod) {{
    if (!cupons.includes(b.coupon)) continue;
    if (fonteFilter && (b.fonte||'ONLINE').toUpperCase() !== fonteFilter) continue;
    stats[b.coupon].usos    += 1;
    stats[b.coupon].receita += b.valor;
    stats[b.coupon].pax     += (b.pax || 1);
    stats[b.coupon].tickets.push(b.valor);
  }}

  // Tabela comparativa
  const headEl = document.getElementById('cupom-comparar-head');
  const bodyEl = document.getElementById('cupom-comparar-body');
  if (headEl) {{
    headEl.innerHTML = '<th>Métrica</th>' +
      cupons.map((c,i) => `<th style="text-align:right;color:${{CUPOM_COLORS[i%CUPOM_COLORS.length]}}">${{c}}</th>`).join('');
  }}
  const rows = [
    ['Voos Confirmados', c => fN(stats[c].usos)],
    ['Receita Total',    c => fBRL(stats[c].receita)],
    ['Ticket Médio',     c => stats[c].usos ? fBRL(stats[c].receita/stats[c].usos) : '—'],
    ['PAX Total',        c => fN(stats[c].pax)],
  ];
  if (bodyEl) {{
    bodyEl.innerHTML = rows.map(([label, fn]) => {{
      const vals = cupons.map(c => ({{c, v: stats[c].usos ? stats[c].receita/stats[c].usos : 0, raw: fn(c)}}));
      return `<tr><td style="color:#94a3b8;font-size:.8rem">${{label}}</td>` +
        cupons.map((c,i) => `<td style="text-align:right;font-weight:600;color:${{CUPOM_COLORS[i%CUPOM_COLORS.length]}}">${{fn(c)}}</td>`).join('') +
        '</tr>';
    }}).join('');
  }}

  // Gráfico de barras
  const datasets = [
    {{ label:'Voos', data: cupons.map(c => stats[c].usos), backgroundColor: cupons.map((_,i) => CUPOM_COLORS[i%CUPOM_COLORS.length]+'cc') }},
  ];
  makeChart('chartCupomComparacao', {{
    type: 'bar',
    data: {{ labels: cupons, datasets }},
    options: {{
      responsive:true, maintainAspectRatio:true,
      plugins:{{ legend:{{display:false}}, tooltip:{{callbacks:{{
        afterLabel: (ctx) => 'Receita: ' + fBRL(stats[cupons[ctx.dataIndex]].receita)
      }}}} }},
      scales:{{ y:{{ beginAtZero:true, ticks:{{stepSize:1}} }} }},
    }}
  }});
}}

function renderCupons(from, to) {{
  const fonteFilter  = (document.getElementById('cupom-detail-filter-fonte')  || {{}}).value || '';
  const allInPeriod  = VOOS_CUPOM.filter(b => b.data >= from && b.data <= to);
  const allCupons    = [...new Set(allInPeriod.map(b => b.coupon))].sort();

  // Remove cupons que sumiram do período
  for (const c of selectedCupons) {{ if (!allCupons.includes(c)) selectedCupons.delete(c); }}

  _buildPills(allCupons);

  const activeSel = [...selectedCupons];
  const filtered = allInPeriod.filter(b =>
    (!fonteFilter || (b.fonte||'ONLINE').toUpperCase() === fonteFilter) &&
    (activeSel.length === 0 || activeSel.includes(b.coupon))
  );

  // Agrega por cupom (confirmados)
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

  // ── Painel de comparação (ativa com 2+ cupons selecionados) ──────────────
  _renderComparacao([...selectedCupons], allInPeriod, fonteFilter);

  // ── Status por cupom (todos os status, período filtrado por data de criação) ──
  const statusBody = document.getElementById('cupom-status-body');
  if (statusBody) {{
    statusBody.innerHTML = CUPOM_STATUS
      .filter(cs => {{
        // inclui apenas cupons que têm ao menos 1 booking no período (via confirmados filtrados)
        const cuponsNoPeriodo = new Set(filtered.map(b => b.coupon));
        return cuponsNoPeriodo.has(cs.cupom) || cs.conf > 0 || cs.aband > 0 || cs.canc > 0;
      }})
      .filter(cs => new Set(filtered.map(b => b.coupon)).has(cs.cupom))
      .map(cs => {{
        const taxa = cs.total ? Math.round(cs.conf / cs.total * 100) : 0;
        const taxaColor = taxa >= 60 ? '#22c55e' : taxa >= 40 ? '#f59e0b' : '#ef4444';
        return `<tr>
          <td><span class="badge badge-blue" style="font-size:.82rem;padding:3px 10px">${{cs.cupom}}</span></td>
          <td style="text-align:right;font-weight:700;color:#22c55e">${{cs.conf}}</td>
          <td style="text-align:right;color:#ef4444">${{cs.aband}}</td>
          <td style="text-align:right;color:#94a3b8">${{cs.canc}}</td>
          <td style="text-align:right;font-weight:600">${{cs.total}}</td>
          <td style="text-align:right;font-weight:700;color:${{taxaColor}}">${{taxa}}%</td>
        </tr>`;
      }}).join('');
  }}

  // Resumo por cupom (confirmados)
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
        <td style="font-family:monospace;font-size:.78rem">${{escHtml(b.numero)}}</td>
        <td><span class="badge badge-blue">${{escHtml(b.coupon)}}</span></td>
        <td style="font-weight:500;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${{escHtml(b.produto)}}">${{escHtml(b.produto)}}</td>
        <td style="text-align:right">${{b.pax || '—'}}</td>
        <td style="text-align:right;color:#22c55e;font-weight:600">${{fBRL(b.valor)}}</td>
        <td style="color:#94a3b8">${{fDate(b.data)}}</td>
        <td style="color:#94a3b8">${{b.tour_dt ? fDate(b.tour_dt) : '—'}}</td>
        <td style="font-size:.75rem;color:#94a3b8">${{escHtml(b.fonte || 'ONLINE')}}</td>
        <td style="color:#94a3b8;font-size:.8rem;max-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${{escHtml(b.nome)}}">${{escHtml(b.nome)}}</td>
      </tr>`).join('');
  }}
}}

let _lastBookingsFiltered = [];

function renderBookings(from, to) {{
  const tbody = document.getElementById('book-body');
  if (!tbody) return;
  const statusFilter = (document.getElementById('book-filter-status') || {{}}).value || '';
  const searchVal    = ((document.getElementById('book-search') || {{}}).value || '').toLowerCase().trim();
  const filtered = BOOKINGS.filter(b => {{
    if (b.d < from || b.d > to) return false;
    if (statusFilter && b.s !== statusFilter) return false;
    if (searchVal) {{
      const haystack = (b.n + ' ' + b.p + ' ' + (b.f||'')).toLowerCase();
      if (!haystack.includes(searchVal)) return false;
    }}
    return true;
  }});
  _lastBookingsFiltered = filtered;
  setText('book-count', filtered.length + ' resultados');
  const rows = filtered.slice(0, 300);
  tbody.innerHTML = rows.map(b => {{
    const sc   = b.s==='CONFIRMED'?'badge-green':b.s==='ABANDONED_CART'?'badge-red':'badge-amber';
    const flag = countryFlag(b.cc);
    const pEsc = escHtml(b.p);
    return `<tr>
      <td style="font-family:monospace;font-size:.78rem">${{escHtml(b.n)}}</td>
      <td><span class="badge ${{sc}}">${{b.s.replace(/_/g,' ')}}</span></td>
      <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${{pEsc}}">${{pEsc}}</td>
      <td style="text-align:right;color:#94a3b8">${{b.px||1}}</td>
      <td style="text-align:right;font-weight:500">${{fBRL(b.v)}}</td>
      <td style="color:#94a3b8">${{fDate(b.d)}}</td>
      <td style="color:#06b6d4">${{b.t ? fDate(b.t) : '—'}}</td>
      <td style="font-size:.75rem;color:#94a3b8">${{escHtml(b.f||'ONLINE')}}</td>
      <td style="font-size:.8rem" title="${{escHtml(b.cc||'')}}">${{flag}} ${{countryName(b.cc)}}</td>
    </tr>`;
  }}).join('');
  if (filtered.length > 300) {{
    tbody.innerHTML += `<tr><td colspan="9" style="text-align:center;color:#94a3b8;padding:12px">… e mais ${{filtered.length-300}} reservas. Use a busca ou filtre por status.</td></tr>`;
  }}
}}

function exportCSV() {{
  const rows = _lastBookingsFiltered.length ? _lastBookingsFiltered
    : BOOKINGS.filter(b => b.d >= currentFrom && b.d <= currentTo);
  const header = ['Nº Pedido','Status','Produto','PAX','Valor','Reservado em','Voo em','Fonte','País'];
  const lines = [header.join(';')];
  for (const b of rows) {{
    lines.push([
      b.n, b.s, '"'+String(b.p||'').replace(/"/g,'""')+'"',
      b.px||1, String(b.v).replace('.',','),
      fDate(b.d), b.t ? fDate(b.t) : '',
      b.f||'ONLINE', b.cc||''
    ].join(';'));
  }}
  const blob = new Blob(['﻿'+lines.join('\\n')], {{type:'text/csv;charset=utf-8'}});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'bookings_'+currentFrom+'_'+currentTo+'.csv';
  a.click(); URL.revokeObjectURL(url);
}}

function countryFlag(cc) {{
  if (!cc || cc.length !== 2) return '';
  return cc.toUpperCase().replace(/./g, c =>
    String.fromCodePoint(0x1F1E6 - 65 + c.charCodeAt(0)));
}}

const COUNTRY_NAMES = {{
  'AF':'Afeganistão','AL':'Albânia','DZ':'Argélia','AD':'Andorra','AO':'Angola',
  'AG':'Antígua e Barbuda','AR':'Argentina','AM':'Armênia','AU':'Austrália',
  'AT':'Áustria','AZ':'Azerbaijão','BS':'Bahamas','BH':'Bahrein','BD':'Bangladesh',
  'BB':'Barbados','BY':'Bielorrússia','BE':'Bélgica','BZ':'Belize','BJ':'Benin',
  'BT':'Butão','BO':'Bolívia','BA':'Bósnia e Herzegovina','BW':'Botsuana',
  'BR':'Brasil','BN':'Brunei','BG':'Bulgária','BF':'Burkina Faso','BI':'Burundi',
  'CV':'Cabo Verde','KH':'Camboja','CM':'Camarões','CA':'Canadá','CF':'Rep. Centro-Africana',
  'TD':'Chade','CL':'Chile','CN':'China','CO':'Colômbia','KM':'Comores',
  'CG':'Congo','CD':'Congo (RDC)','CR':'Costa Rica','HR':'Croácia','CU':'Cuba',
  'CY':'Chipre','CZ':'República Tcheca','DK':'Dinamarca','DJ':'Djibuti',
  'DM':'Dominica','DO':'República Dominicana','EC':'Equador','EG':'Egito',
  'SV':'El Salvador','GQ':'Guiné Equatorial','ER':'Eritreia','EE':'Estônia',
  'SZ':'Eswatini','ET':'Etiópia','FJ':'Fiji','FI':'Finlândia','FR':'França',
  'GA':'Gabão','GM':'Gâmbia','GE':'Geórgia','DE':'Alemanha','GH':'Gana',
  'GR':'Grécia','GD':'Granada','GT':'Guatemala','GN':'Guiné','GW':'Guiné-Bissau',
  'GY':'Guiana','HT':'Haiti','HN':'Honduras','HU':'Hungria','IS':'Islândia',
  'IN':'Índia','ID':'Indonésia','IR':'Irã','IQ':'Iraque','IE':'Irlanda',
  'IL':'Israel','IT':'Itália','JM':'Jamaica','JP':'Japão','JO':'Jordânia',
  'KZ':'Cazaquistão','KE':'Quênia','KI':'Kiribati','KP':'Coreia do Norte',
  'KR':'Coreia do Sul','KW':'Kuwait','KG':'Quirguistão','LA':'Laos','LV':'Letônia',
  'LB':'Líbano','LS':'Lesoto','LR':'Libéria','LY':'Líbia','LI':'Liechtenstein',
  'LT':'Lituânia','LU':'Luxemburgo','MG':'Madagascar','MW':'Malawi','MY':'Malásia',
  'MV':'Maldivas','ML':'Mali','MT':'Malta','MH':'Ilhas Marshall','MR':'Mauritânia',
  'MU':'Maurício','MX':'México','FM':'Micronésia','MD':'Moldávia','MC':'Mônaco',
  'MN':'Mongólia','ME':'Montenegro','MA':'Marrocos','MZ':'Moçambique','MM':'Myanmar',
  'NA':'Namíbia','NR':'Nauru','NP':'Nepal','NL':'Países Baixos','NZ':'Nova Zelândia',
  'NI':'Nicarágua','NE':'Níger','NG':'Nigéria','MK':'Macedônia do Norte','NO':'Noruega',
  'OM':'Omã','PK':'Paquistão','PW':'Palau','PA':'Panamá','PG':'Papua Nova Guiné',
  'PY':'Paraguai','PE':'Peru','PH':'Filipinas','PL':'Polônia','PT':'Portugal',
  'QA':'Catar','RO':'Romênia','RU':'Rússia','RW':'Ruanda','KN':'São Cristóvão e Nevis',
  'LC':'Santa Lúcia','VC':'São Vicente e Granadinas','WS':'Samoa','SM':'San Marino',
  'ST':'São Tomé e Príncipe','SA':'Arábia Saudita','SN':'Senegal','RS':'Sérvia',
  'SC':'Seicheles','SL':'Serra Leoa','SG':'Singapura','SK':'Eslováquia','SI':'Eslovênia',
  'SB':'Ilhas Salomão','SO':'Somália','ZA':'África do Sul','SS':'Sudão do Sul',
  'ES':'Espanha','LK':'Sri Lanka','SD':'Sudão','SR':'Suriname','SE':'Suécia',
  'CH':'Suíça','SY':'Síria','TW':'Taiwan','TJ':'Tajiquistão','TZ':'Tanzânia',
  'TH':'Tailândia','TL':'Timor-Leste','TG':'Togo','TO':'Tonga','TT':'Trinidad e Tobago',
  'TN':'Tunísia','TR':'Turquia','TM':'Turcomenistão','TV':'Tuvalu','UG':'Uganda',
  'UA':'Ucrânia','AE':'Emirados Árabes','GB':'Reino Unido','US':'Estados Unidos',
  'UY':'Uruguai','UZ':'Uzbequistão','VU':'Vanuatu','VE':'Venezuela','VN':'Vietnã',
  'YE':'Iêmen','ZM':'Zâmbia','ZW':'Zimbábue','HK':'Hong Kong','MO':'Macau',
  'TW':'Taiwan','PS':'Palestina','XK':'Kosovo','??':'Desconhecido',
}};

function countryName(cc) {{
  if (!cc) return 'Desconhecido';
  return COUNTRY_NAMES[cc.toUpperCase()] || cc.toUpperCase();
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
      <td><span style="margin-right:6px">${{flag}}</span>${{countryName(cc)}}</td>
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
        <td><span style="margin-right:6px">${{flag}}</span>${{countryName(c.cc)}}</td>
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
      const tip = v ? `${{v}} reserva${{v>1?'s':''}} feitas em ${{fmtYM(cm)}} para voos em ${{fmtYM(tm)}}` : '';
      tbl += `<td title="${{tip}}" style="padding:6px 8px;text-align:center;border-radius:4px;${{heatColor(v)}};min-width:44px;cursor:${{v?'default':''}}">${{v||''}}</td>`;
    }}
    tbl += '</tr>';
  }}
  tbl += '</tbody></table>';
  const el = document.getElementById('heatmap-container');
  if (el) el.innerHTML = tbl;
}}

// ─── Meta Orgânico ────────────────────────────────────────────────────────────
let _orgPosts = [];

function renderOrganico(from, to) {{
  if (!ORGANICO || !ORGANICO.length) return;
  const posts = ORGANICO.filter(p => p.criado_em >= from && p.criado_em <= to);
  const fb = posts.filter(p => p.plataforma === 'facebook');
  const ig = posts.filter(p => p.plataforma === 'instagram');

  const sum  = (arr, f) => arr.reduce((s, p) => s + (p[f] || 0), 0);
  const engFb = p => (p.curtidas||0) + (p.comentarios||0) + (p.compartilhamentos||0) + (p.engajados||0);
  const engIg = p => (p.curtidas||0) + (p.comentarios||0) + (p.salvos||0);

  setText('org-fb-posts',   fb.length);
  setText('org-ig-posts',   ig.length);
  setText('org-fb-alcance', fN(sum(fb, 'alcance')));
  setText('org-ig-alcance', fN(sum(ig, 'alcance')));
  setText('org-fb-impr',    fN(sum(fb, 'impressoes')));
  setText('org-ig-impr',    fN(sum(ig, 'impressoes')));
  setText('org-fb-eng',     fb.length ? fN(Math.round(fb.reduce((s,p)=>s+engFb(p),0)/fb.length)) : '—');
  setText('org-ig-eng',     ig.length ? fN(Math.round(ig.reduce((s,p)=>s+engIg(p),0)/ig.length)) : '—');

  // Atualiza filtro de tipos
  const tipos = [...new Set(posts.map(p => p.tipo))].sort();
  const tipoSel = document.getElementById('org-filter-tipo');
  if (tipoSel) {{
    const prev = tipoSel.value;
    tipoSel.innerHTML = '<option value="">Todos os tipos</option>' +
      tipos.map(t => `<option value="${{t}}"${{t===prev?' selected':''}}>${{t}}</option>`).join('');
  }}

  _orgPosts = posts;
  renderOrganicoPosts();
  buildOrganicoCharts(fb, ig, posts);
}}

function renderOrganicoPosts() {{
  const plat = (document.getElementById('org-filter-plataforma')||{{}}).value || '';
  const tipo = (document.getElementById('org-filter-tipo')||{{}}).value || '';
  const sort = (document.getElementById('org-sort')||{{}}).value || 'alcance';

  let posts = _orgPosts.filter(p =>
    (!plat || p.plataforma === plat) &&
    (!tipo || p.tipo === tipo)
  );
  posts = [...posts].sort((a, b) => {{
    if (sort === 'criado_em') return (b.criado_em > a.criado_em) ? 1 : -1;
    return (b[sort] || 0) - (a[sort] || 0);
  }});

  const tbody = document.getElementById('org-posts-body');
  if (!tbody) return;
  if (!posts.length) {{
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#94a3b8;padding:24px">Nenhum post no período.</td></tr>';
    return;
  }}
  const engFb = p => (p.curtidas||0) + (p.comentarios||0) + (p.compartilhamentos||0) + (p.engajados||0);
  const engIg = p => (p.curtidas||0) + (p.comentarios||0) + (p.salvos||0);

  tbody.innerHTML = posts.map(p => {{
    const isFb      = p.plataforma === 'facebook';
    const platColor = isFb ? '#1877f2' : '#e1306c';
    const platLbl   = isFb ? 'FB' : 'IG';
    const salvComp  = isFb ? fN(p.compartilhamentos||0) : fN(p.salvos||0);
    const totalEng  = isFb ? engFb(p) : engIg(p);
    const msgEsc    = escHtml(p.mensagem||'—');
    return `<tr>
      <td><span class="badge" style="background:${{platColor}}22;color:${{platColor}};font-weight:700">${{platLbl}}</span></td>
      <td style="font-size:.75rem;color:#94a3b8;text-transform:capitalize">${{escHtml(p.tipo||'')}}</td>
      <td style="color:#94a3b8;white-space:nowrap">${{fDate(p.criado_em)}}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8rem" title="${{msgEsc}}">${{msgEsc}}</td>
      <td style="text-align:right;font-weight:600">${{fN(p.alcance||0)}}</td>
      <td style="text-align:right;color:#94a3b8">${{fN(p.impressoes||0)}}</td>
      <td style="text-align:right;color:#f59e0b">${{fN(p.curtidas||0)}}</td>
      <td style="text-align:right;color:#94a3b8">${{fN(p.comentarios||0)}}</td>
      <td style="text-align:right;color:#22c55e">${{salvComp}}</td>
      <td style="text-align:right;color:#06b6d4;font-weight:600">${{fN(totalEng)}}</td>
    </tr>`;
  }}).join('');
}}

function buildOrganicoCharts(fb, ig, posts) {{
  const engFb = p => (p.curtidas||0) + (p.comentarios||0) + (p.compartilhamentos||0) + (p.engajados||0);
  const engIg = p => (p.curtidas||0) + (p.comentarios||0) + (p.salvos||0);
  const avgArr = (arr, fn) => arr.length ? arr.reduce((s,p)=>s+fn(p),0)/arr.length : 0;

  // Gráfico 1 — Comparativo FB vs IG (médias)
  makeChart('chartOrgComparativo', {{
    type: 'bar',
    data: {{
      labels: ['Alcance Médio', 'Impressões Médias', 'Eng. Médio'],
      datasets: [
        {{ label:'Facebook', backgroundColor:'rgba(24,119,242,.75)', borderRadius:4,
           data: [Math.round(avgArr(fb,p=>p.alcance||0)), Math.round(avgArr(fb,p=>p.impressoes||0)), Math.round(avgArr(fb,engFb))] }},
        {{ label:'Instagram', backgroundColor:'rgba(225,48,108,.75)', borderRadius:4,
           data: [Math.round(avgArr(ig,p=>p.alcance||0)), Math.round(avgArr(ig,p=>p.impressoes||0)), Math.round(avgArr(ig,engIg))] }},
      ]
    }},
    options:{{ responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true}}}} }}
  }});

  // Gráfico 2 — Posts por semana FB vs IG
  const timeMap = {{}};
  for (const p of posts) {{
    const dt = new Date(p.criado_em + 'T12:00:00');
    dt.setDate(dt.getDate() - dt.getDay());
    const key = dt.toISOString().slice(0,10);
    if (!timeMap[key]) timeMap[key] = {{fb:0, ig:0}};
    timeMap[key][p.plataforma==='instagram'?'ig':'fb']++;
  }}
  const tKeys = Object.keys(timeMap).sort();
  makeChart('chartOrgTimeline', {{
    type:'bar',
    data:{{ labels:tKeys.map(k=>k.slice(5)),
      datasets:[
        {{label:'Facebook',  data:tKeys.map(k=>timeMap[k].fb), backgroundColor:'rgba(24,119,242,.7)', borderRadius:3, stack:'s'}},
        {{label:'Instagram', data:tKeys.map(k=>timeMap[k].ig), backgroundColor:'rgba(225,48,108,.7)', borderRadius:3, stack:'s'}},
      ] }},
    options:{{ responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:14}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true,ticks:{{stepSize:1}}}}}} }}
  }});

  // Gráfico 3 — Engajamento médio por tipo de post
  const tipoMap = {{}};
  for (const p of posts) {{
    const t = p.tipo || 'outro';
    if (!tipoMap[t]) tipoMap[t] = {{total:0, count:0}};
    tipoMap[t].total += p.plataforma==='instagram' ? engIg(p) : engFb(p);
    tipoMap[t].count++;
  }}
  const tipoEntries = Object.entries(tipoMap).sort((a,b)=>(b[1].total/b[1].count)-(a[1].total/a[1].count));
  const COLORS = ['rgba(99,102,241,.75)','rgba(34,197,94,.75)','rgba(245,158,11,.75)','rgba(6,182,212,.75)','rgba(236,72,153,.75)'];
  makeChart('chartOrgTipos', {{
    type:'bar',
    data:{{ labels:tipoEntries.map(([t])=>t),
      datasets:[{{ label:'Eng. Médio',
        data:tipoEntries.map(([,v])=>Math.round(v.total/v.count)),
        backgroundColor:tipoEntries.map((_,i)=>COLORS[i%COLORS.length]), borderRadius:4 }}] }},
    options:{{ indexAxis:'y', responsive:true, plugins:{{legend:{{display:false}}}},
      scales:{{x:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true}},y:{{grid:{{display:false}}}}}} }}
  }});

  // Gráfico 4 — Alcance semanal FB vs IG
  const alcMap = {{}};
  for (const p of posts) {{
    const dt = new Date(p.criado_em + 'T12:00:00');
    dt.setDate(dt.getDate() - dt.getDay());
    const key = dt.toISOString().slice(0,10);
    if (!alcMap[key]) alcMap[key] = {{fb:0, ig:0}};
    alcMap[key][p.plataforma==='instagram'?'ig':'fb'] += (p.alcance||0);
  }}
  const aKeys = Object.keys(alcMap).sort();
  makeChart('chartOrgAlcance', {{
    type:'line',
    data:{{ labels:aKeys.map(k=>k.slice(5)),
      datasets:[
        {{label:'Facebook',  data:aKeys.map(k=>alcMap[k].fb), borderColor:'#1877f2', backgroundColor:'rgba(24,119,242,.1)', fill:true, tension:0.4, pointRadius:2}},
        {{label:'Instagram', data:aKeys.map(k=>alcMap[k].ig), borderColor:'#e1306c', backgroundColor:'rgba(225,48,108,.1)', fill:true, tension:0.4, pointRadius:2}},
      ] }},
    options:{{ responsive:true, interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{labels:{{boxWidth:12}}}}}},
      scales:{{x:{{grid:{{display:false}},ticks:{{maxTicksLimit:14}}}},y:{{grid:{{color:'rgba(51,65,85,.4)'}},beginAtZero:true}}}} }}
  }});
}}

// ─── Init flatpickr ───────────────────────────────────────────────────────────
// ─── Card collapse ────────────────────────────────────────────────────────────
function toggleCard(bodyId, btnId) {{
  const body = document.getElementById(bodyId);
  const btn  = document.getElementById(btnId);
  if (!body) return;
  const hidden = body.style.display === 'none';
  body.style.display = hidden ? '' : 'none';
  if (btn) btn.textContent = hidden ? '▲ Minimizar' : '▼ Expandir';
}}

flatpickr.localize(flatpickr.l10ns.pt);
flatpickr("#date-range", {{
  mode: "range",
  dateFormat: "Y-m-d",
  altInput: true,
  altFormat: "d-m-Y",
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

// ─── Receita histórica — Month by Month / Previous Year Comparison ───────────
function buildReceitaHistorico() {{
  const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];

  // Paleta e estilo por ano (ano mais recente = linha cheia, anteriores = tracejadas)
  const YEAR_STYLE = [
    {{ color: '#22c55e', width: 2.5, dash: [],     fill: '#22c55e12', radius: 4 }},
    {{ color: '#6366f1', width: 2,   dash: [6,3],  fill: false,       radius: 3 }},
    {{ color: '#f59e0b', width: 2,   dash: [4,4],  fill: false,       radius: 3 }},
    {{ color: '#ef4444', width: 1.5, dash: [3,3],  fill: false,       radius: 3 }},
  ];

  // Agrupa receita confirmada pelo mês do VOO (tour date = fulfillment)
  // Fallback para data de criação se não houver tour date
  const byYearMo = {{}};
  for (const b of BOOKINGS) {{
    if (b.s !== 'CONFIRMED') continue;
    const dateStr = b.t || b.d;
    if (!dateStr) continue;
    const yr = dateStr.slice(0, 4);
    const mo = parseInt(dateStr.slice(5, 7), 10) - 1; // 0-based
    if (!byYearMo[yr]) byYearMo[yr] = new Array(12).fill(null);
    byYearMo[yr][mo] = (byYearMo[yr][mo] || 0) + (b.v || 0);
  }}

  // Ordena anos — mais recente primeiro para legenda, mas datasets do mais antigo ao mais novo
  const yearsDesc = Object.keys(byYearMo).sort().reverse();
  const yearsAsc  = [...yearsDesc].reverse();

  const datasets = yearsAsc.map((yr, idx) => {{
    const styleIdx = yearsAsc.length - 1 - idx; // mais recente = índice 0 no estilo
    const s = YEAR_STYLE[Math.min(styleIdx, YEAR_STYLE.length - 1)];
    return {{
      label: yr,
      data: byYearMo[yr].map(v => v === null ? null : Math.round(v * 100) / 100),
      borderColor: s.color,
      backgroundColor: s.fill || 'transparent',
      pointBackgroundColor: s.color,
      pointRadius: s.radius,
      pointHoverRadius: s.radius + 2,
      borderWidth: s.width,
      borderDash: s.dash,
      tension: 0.35,
      fill: !!s.fill,
      spanGaps: false,
    }};
  }});

  makeChart('chartReceitaHistorico', {{
    type: 'line',
    data: {{ labels: MESES, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: ctx => ctx.parsed.y !== null
              ? ' ' + ctx.dataset.label + ': ' + fBRL(ctx.parsed.y)
              : ' ' + ctx.dataset.label + ': —',
          }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ color: 'rgba(51,65,85,.3)' }} }},
        y: {{
          beginAtZero: true,
          grid: {{ color: 'rgba(51,65,85,.4)' }},
          ticks: {{ callback: v => v >= 1000000
            ? 'R$' + (v/1000000).toFixed(1) + 'M'
            : 'R$' + (v/1000).toFixed(0) + 'k'
          }},
        }}
      }}
    }}
  }});

  // Legenda manual
  const togglesEl = document.getElementById('hist-year-toggles');
  if (togglesEl) {{
    togglesEl.innerHTML = yearsDesc.map((yr, i) => {{
      const s = YEAR_STYLE[Math.min(i, YEAR_STYLE.length - 1)];
      const dashStyle = s.dash.length
        ? `border-top: 2px dashed ${{s.color}}`
        : `border-top: 2.5px solid ${{s.color}}`;
      return `<span style="display:inline-flex;align-items:center;gap:5px;font-size:.75rem;color:var(--sub)">
        <span style="display:inline-block;width:22px;height:0;${{dashStyle}}"></span>
        <span style="font-weight:${{i===0?'700':'400'}};color:${{i===0?s.color:'var(--sub)'}}">${{yr}}</span>
      </span>`;
    }}).join('');
  }}
}};

// ─── Init com últimos 30d ─────────────────────────────────────────────────────
applyDateRange(D30_FROM, HOJE);
renderHeatmap();
buildReceitaHistorico();
</script>
</body>
</html>"""
    return html


# ─── Main ─────────────────────────────────────────────────────────────────────
def _extrair_meta_do_html():
    """Lê META_DATA, CAMPS_DIARIO e CRIATIVOS do index.html existente (fallback)."""
    import re
    try:
        with open(ARQUIVO_HTML, encoding="utf-8") as f:
            src = f.read()
        def _extract(var):
            m = re.search(rf'const {var}\s*=\s*(\{{.*?\}});', src, re.S)
            if not m:
                m = re.search(rf'const {var}\s*=\s*(\[.*?\]);', src, re.S)
            return json.loads(m.group(1)) if m else None
        meta       = _extract("META_DATA")
        camps_d    = _extract("CAMPS_DIARIO")
        criativos  = _extract("CRIATIVOS_PERIODOS")
        return meta, camps_d, criativos
    except Exception as e:
        print(f"       AVISO: não foi possível extrair Meta do HTML: {e}")
        return None, None, None


def main():
    import sys
    rezdy_only = "--rezdy-only" in sys.argv
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Vertical Rio Dashboard — {agora} ===\n")

    if rezdy_only:
        print("[META ] Modo --rezdy-only: reutilizando dados Meta do HTML atual...")
        meta, camps_diario, criativos = _extrair_meta_do_html()
        if not meta:
            print("       ERRO: não encontrou META_DATA no HTML. Rode sem --rezdy-only.")
            sys.exit(1)
        print(f"       Meta carregado do HTML existente.")
    else:
        print("[ 1/8 ] Meta Ads — resumo 30d (API)...")
        d30 = buscar_meta_periodo("last_30d")
        print(f"       Gasto R${d30['gasto']:,.2f} | CTR {d30['ctr']}% | Conv.Inic. {d30['conversas']}")

        print("[ 2/8 ] Meta Ads — campanhas 30d...")
        campanhas = buscar_meta_campanhas("last_30d")
        print(f"       {len(campanhas)} campanhas")

        print("[ 3/8 ] Meta Ads — diario conta 90d...")
        diario = buscar_meta_diario(90)
        print(f"       {len(diario)} dias")

        print("[ 4/8 ] Meta Ads — diário por campanha 90d...")
        camps_diario = buscar_meta_diario_campanhas(90)
        print(f"       {len(camps_diario)} campanhas × 90d")

        print("[ 5/8 ] Meta Ads — criativos 4 períodos (7d/14d/30d/90d)...")
        criativos_d7  = buscar_meta_criativos("last_7d")
        criativos_d14 = buscar_meta_criativos("last_14d")
        criativos_d30 = buscar_meta_criativos("last_30d")
        criativos_d90 = buscar_meta_criativos("last_90d")
        criativos = {"d7": criativos_d7, "d14": criativos_d14, "d30": criativos_d30, "d90": criativos_d90}
        print(f"       {len(criativos_d30)} criativos ativos (30d)")

        meta = {"d30": d30, "campanhas": campanhas, "diario": diario}

    print("[ 6/8 ] Meta Orgânico — descobrindo páginas e posts...")
    organico_fb, organico_ig = [], []
    try:
        paginas = buscar_paginas()
        if not paginas:
            print("       Nenhuma página retornada — dados orgânicos não disponíveis.")
        else:
            page       = paginas[0]
            page_id    = page["id"]
            page_token = page.get("access_token", META_TOKEN)
            ig_info    = page.get("instagram_business_account") or {}
            ig_id      = ig_info.get("id", "")
            print(f"       Página: {page.get('name','?')} (id={page_id})")
            try:
                organico_fb = buscar_organico_facebook(page_id, page_token, 90)
                print(f"       {len(organico_fb)} posts Facebook")
            except Exception as e_fb:
                print(f"       AVISO Facebook orgânico: {e_fb}")
            if ig_id:
                try:
                    organico_ig = buscar_organico_instagram(ig_id, 90)
                    print(f"       {len(organico_ig)} posts Instagram")
                except Exception as e_ig:
                    print(f"       AVISO Instagram (sem permissão instagram_basic): {type(e_ig).__name__}")
            else:
                print("       Instagram Business Account não encontrado na página.")
    except Exception as e:
        print(f"       AVISO geral orgânico: {e}")

    print("[ 7/8 ] Rezdy — reservas (histórico completo)...")
    reservas = buscar_rezdy_reservas(5000, date_start="2019-01-01")
    print(f"       {len(reservas)} reservas")

    print("[ 8/8 ] Processando e gerando HTML...")
    rezdy_dados = processar_rezdy(reservas)
    data_min = rezdy_dados["por_dia"][0]["data"] if rezdy_dados["por_dia"] else "?"
    print(f"       {data_min} a hoje: {rezdy_dados['confirmadas']} conf | R${rezdy_dados['receita']:,.2f} | {len(rezdy_dados['todos_bookings'])} bookings")

    html = gerar_html(meta, rezdy_dados, camps_diario, criativos, agora, organico_fb, organico_ig)

    with open(ARQUIVO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nOK: {ARQUIVO_HTML} gerado ({len(html):,} chars)")


if __name__ == "__main__":
    main()
