#!/usr/bin/env python3
"""
Fetch Meta Ads data and update META_DATA in index.html.
Env: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID
Run: python scripts/update_meta_data.py
"""
import os, re, sys, json, requests
from datetime import datetime, timedelta

ACCESS_TOKEN  = os.environ.get("META_ACCESS_TOKEN", "")
AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID", "")
API_VERSION   = "v19.0"
BASE_URL      = f"https://graph.facebook.com/{API_VERSION}"
SCRIPT_DIR    = os.path.dirname(__file__)
HTML_FILE     = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "index.html"))

if not ACCESS_TOKEN or not AD_ACCOUNT_ID:
    sys.exit("ERROR: META_ACCESS_TOKEN and META_AD_ACCOUNT_ID must be set.")


def api_get(endpoint, params=None):
    p = {"access_token": ACCESS_TOKEN, **(params or {})}
    r = requests.get(f"{BASE_URL}/{endpoint}", params=p, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Meta API {r.status_code}: {r.text[:300]}")
    return r.json()


MSG_ACTIONS = {
    "onsite_conversion.total_messaging_connection":        "conexoes",
    "onsite_conversion.messaging_first_reply":             "first_reply",
    "onsite_conversion.messaging_conversation_started_7d": "conversas",
    "onsite_conversion.messaging_block":                   "bloqueios",
}


def extract_actions(actions, keys=None):
    out = {v: 0 for v in MSG_ACTIONS.values()}
    out["compras_meta"] = 0
    for a in (actions or []):
        at = a.get("action_type", "")
        val = int(float(a.get("value", 0) or 0))
        if at in MSG_ACTIONS:
            out[MSG_ACTIONS[at]] += val
        if at in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"):
            out["compras_meta"] += val
    return out


def fetch_account_d30():
    resp = api_get(f"{AD_ACCOUNT_ID}/insights", {
        "level":       "account",
        "fields":      "spend,impressions,clicks,reach,ctr,cpc,cpm,actions,action_values",
        "date_preset": "last_30d",
        "limit":       1,
    })
    row = (resp.get("data") or [{}])[0]
    acts = extract_actions(row.get("actions", []))

    roas = 0.0
    for av in (row.get("action_values") or []):
        if av.get("action_type") in ("purchase", "omni_purchase",
                                     "offsite_conversion.fb_pixel_purchase"):
            gasto = float(row.get("spend") or 1)
            roas = round(float(av.get("value", 0)) / gasto, 2) if gasto else 0.0

    return {
        "gasto":       round(float(row.get("spend") or 0), 2),
        "impressoes":  int(row.get("impressions") or 0),
        "cliques":     int(row.get("clicks") or 0),
        "alcance":     int(row.get("reach") or 0),
        "ctr":         round(float(row.get("ctr") or 0), 2),
        "cpc":         round(float(row.get("cpc") or 0), 2),
        "cpm":         round(float(row.get("cpm") or 0), 2),
        "conexoes":    acts["conexoes"],
        "first_reply": acts["first_reply"],
        "conversas":   acts["conversas"],
        "bloqueios":   acts["bloqueios"],
        "compras_meta":acts["compras_meta"],
        "roas":        roas,
    }


def fetch_campanhas():
    campos = ("campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,reach,actions")
    dados, resp = [], api_get(f"{AD_ACCOUNT_ID}/insights", {
        "level":       "campaign",
        "fields":      campos,
        "date_preset": "last_30d",
        "limit":       200,
    })
    dados.extend(resp.get("data", []))
    while resp.get("paging", {}).get("next"):
        resp = requests.get(resp["paging"]["next"], timeout=30).json()
        dados.extend(resp.get("data", []))

    campanhas = []
    for c in sorted(dados, key=lambda x: -float(x.get("spend") or 0)):
        gasto   = round(float(c.get("spend") or 0), 2)
        cliques = int(c.get("clicks") or 0)
        acts    = extract_actions(c.get("actions", []))
        conexoes = acts["conexoes"]
        adicao   = 0
        for a in (c.get("actions") or []):
            if a.get("action_type") in ("add_to_cart", "omni_add_to_cart"):
                adicao += int(float(a.get("value", 0) or 0))

        campanhas.append({
            "nome":              c.get("campaign_name", ""),
            "id":                c.get("campaign_id", ""),
            "gasto":             gasto,
            "impressoes":        int(c.get("impressions") or 0),
            "cliques":           cliques,
            "ctr":               round(float(c.get("ctr") or 0), 2),
            "cpc":               round(float(c.get("cpc") or 0), 2),
            "alcance":           int(c.get("reach") or 0),
            "conexoes":          conexoes,
            "first_reply":       acts["first_reply"],
            "conversas":         acts["conversas"],
            "adicao_carrinho":   adicao,
            "custo_por_msg":     round(gasto / conexoes, 2) if conexoes else 0,
            "custo_por_carrinho":round(gasto / adicao, 2) if adicao else 0,
        })
    return campanhas


def fetch_diario():
    hoje  = datetime.now()
    inicio = hoje - timedelta(days=365)
    dados, resp = [], api_get(f"{AD_ACCOUNT_ID}/insights", {
        "level":          "account",
        "fields":         "spend,impressions,clicks,actions",
        "time_range":     json.dumps({"since": inicio.strftime("%Y-%m-%d"),
                                      "until": hoje.strftime("%Y-%m-%d")}),
        "time_increment": 1,
        "limit":          500,
    })
    dados.extend(resp.get("data", []))
    while resp.get("paging", {}).get("next"):
        resp = requests.get(resp["paging"]["next"], timeout=30).json()
        dados.extend(resp.get("data", []))

    result = []
    for d in dados:
        if float(d.get("spend") or 0) <= 0:
            continue
        acts = extract_actions(d.get("actions", []))
        result.append({
            "data":      d["date_start"],
            "gasto":     round(float(d.get("spend") or 0), 2),
            "impressoes":int(d.get("impressions") or 0),
            "cliques":   int(d.get("clicks") or 0),
            "conexoes":  acts["conexoes"],
            "conversas": acts["conversas"],
        })
    return result


def _objetivo(camp):
    if "SEGUIDORES" in camp:
        return "SEGUIDORES"
    if "[MSG]" in camp:
        return "MSG"
    return "TRAF"


def fetch_criativos_cards():
    """Top 4 ads por objetivo (SEGUIDORES, MSG, TRAF) com thumbnail."""
    dados, resp = [], api_get(f"{AD_ACCOUNT_ID}/insights", {
        "level":       "ad",
        "fields":      "ad_id,ad_name,campaign_name,spend,impressions,clicks,ctr,cpc,actions",
        "date_preset": "last_30d",
        "limit":       500,
    })
    dados.extend(resp.get("data", []))
    while resp.get("paging", {}).get("next"):
        resp = requests.get(resp["paging"]["next"], timeout=30).json()
        dados.extend(resp.get("data", []))

    grupos = {"SEGUIDORES": [], "MSG": [], "TRAF": []}
    for row in dados:
        spend = float(row.get("spend") or 0)
        if spend <= 0:
            continue
        cat  = _objetivo(row.get("campaign_name", ""))
        acts = extract_actions(row.get("actions", []))
        grupos[cat].append({
            "ad_id":   row["ad_id"],
            "nome":    row.get("ad_name", ""),
            "camp":    row.get("campaign_name", ""),
            "gasto":   round(spend, 2),
            "impr":    int(row.get("impressions") or 0),
            "cliques": int(row.get("clicks") or 0),
            "ctr":     round(float(row.get("ctr") or 0), 2),
            "cpc":     round(float(row.get("cpc") or 0), 2),
            "msg":     acts["conexoes"],
            "thumb":   "",
        })

    for cat in grupos:
        grupos[cat].sort(key=lambda x: -x["gasto"])
        grupos[cat] = grupos[cat][:4]

    top_ids = [a["ad_id"] for ads in grupos.values() for a in ads]
    if top_ids:
        try:
            thumb_map = {}
            for i in range(0, len(top_ids), 50):
                batch = top_ids[i:i+50]
                r = api_get("", {
                    "ids":    ",".join(batch),
                    "fields": "id,creative{thumbnail_url,image_url}",
                })
                for ad_id, ad_data in r.items():
                    cr = ad_data.get("creative") or {}
                    thumb_map[ad_id] = cr.get("thumbnail_url") or cr.get("image_url") or ""
            for ads in grupos.values():
                for a in ads:
                    a["thumb"] = thumb_map.get(a["ad_id"], "")
        except Exception as e:
            print(f"  [AVISO] Thumbnails: {e}")

    total = sum(len(v) for v in grupos.values())
    print(f"  {total} criativos com thumb ({len([a for ads in grupos.values() for a in ads if a['thumb']])} com imagem)")
    return grupos


def main():
    print(f"\n=== Meta Ads Update — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===\n")

    print("Buscando resumo d30...")
    d30 = fetch_account_d30()
    print(f"  Gasto: R$ {d30['gasto']:,.2f} | Impressões: {d30['impressoes']:,} | "
          f"Cliques: {d30['cliques']:,} | Conexões: {d30['conexoes']}")

    print("Buscando campanhas (last 30d)...")
    campanhas = fetch_campanhas()
    print(f"  {len(campanhas)} campanhas encontradas")

    print("Buscando dados diários (365d)...")
    diario = fetch_diario()
    print(f"  {len(diario)} dias com gasto")

    print("Buscando criativos com thumbnails...")
    criativos_cards = fetch_criativos_cards()

    meta_data = {"d30": d30, "campanhas": campanhas, "diario": diario, "criativos_cards": criativos_cards}

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(meta_data, ensure_ascii=False, separators=(",", ":"))
    padrao = r"(const META_DATA\s*=\s*)(\{[\s\S]*?\})(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        sys.exit("ERROR: META_DATA not found in index.html")

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(novo_html)

    print(f"\nindex.html atualizado com META_DATA ({len(diario)} dias diários, {len(campanhas)} campanhas)")


if __name__ == "__main__":
    main()
