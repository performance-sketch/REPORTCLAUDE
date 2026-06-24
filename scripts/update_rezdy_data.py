#!/usr/bin/env python3
"""
Fetch confirmed bookings from Rezdy API for May 26 - Jun 23 (2025 & 2026),
regenerate the ORDERS array in analise-rezdy-periodos.html with both
booking date (d) and fulfillment date (df), and update the footer stamp.

Required env var: REZDY_API_KEY
"""
import os, re, sys, json, requests
from datetime import date

API_KEY  = os.environ.get("REZDY_API_KEY", "")
BASE_URL = "https://api.rezdy.com/v1"
HTML_FILE = os.path.join(os.path.dirname(__file__), "..", "analise-rezdy-periodos.html")

if not API_KEY:
    sys.exit("ERROR: REZDY_API_KEY environment variable is not set.")

# Fetch window per year — slightly wider than the display period
# to catch orders created a day or two after Jun 23 with fulfillment in period
FETCH_WINDOWS = [
    {"year": 2025, "min": "2025-05-26", "max": "2025-06-27"},
    {"year": 2026, "min": "2026-05-26", "max": "2026-06-27"},
]


# ── CATEGORISATION ────────────────────────────────────────────────────────────

def get_prod(name: str) -> str:
    n = (name or "").strip()
    if "GYG" in n:
        return "GYG"
    if n == "Doors off | 30min":
        return "30min"
    if n == "Doors off | 45min":
        return "45min"
    return "Other"

def get_src(raw_source: str, prod: str) -> str:
    if prod == "GYG":
        return "GYG"
    s = (raw_source or "").lower()
    if "online" in s:
        return "Online"
    return "Interno"   # Internal, Negotiated Rate, etc.


# ── API FETCHING ───────────────────────────────────────────────────────────────

def fetch_bookings(min_date: str, max_date: str) -> list:
    """Paginate through /v1/bookings for the given date window."""
    all_b, offset, limit = [], 0, 100
    while True:
        resp = requests.get(
            f"{BASE_URL}/bookings",
            params={
                "apiKey":       API_KEY,
                "limit":        limit,
                "offset":       offset,
                "minDateBooked": min_date,
                "maxDateBooked": max_date,
            },
            timeout=30,
        )
        if not resp.ok:
            print(f"  API error {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()

        data  = resp.json()
        batch = data.get("bookings", [])
        all_b.extend(batch)
        print(f"  offset={offset}  got={len(batch)}  total_so_far={len(all_b)}")
        if len(batch) < limit:
            break
        offset += limit
    return all_b


# ── PARSING ────────────────────────────────────────────────────────────────────

def parse_booking(b: dict, year: int) -> dict | None:
    """Convert one Rezdy API booking dict into our dashboard order format."""
    if (b.get("status") or "").upper() != "CONFIRMED":
        return None

    # Booking creation date
    d_raw = b.get("dateCreated") or b.get("dateBooked") or ""
    d = d_raw[:10]
    if not d:
        return None

    # Fulfillment / start date — try local time first, fall back to UTC
    df_raw = (
        b.get("startTimeLocal")
        or b.get("startTime")
        or b.get("startDateTime")
        or ""
    )
    df = df_raw[:10]
    if not df:
        df = d   # fallback: use booking date

    # Product from first line item
    items     = b.get("items") or []
    prod_name = items[0].get("productName", "") if items else ""
    prod      = get_prod(prod_name)

    # Source
    src = get_src(b.get("source", ""), prod)

    # Amounts
    gross = float(b.get("totalAmount") or b.get("totalCost") or 0)

    # Free-of-charge payments
    free = 0.0
    for p in (b.get("payments") or []):
        ptype = ((p.get("type") or p.get("label") or "")).upper()
        if "FREE" in ptype:
            free += float(p.get("amount") or 0)

    net   = round(gross - free, 2)
    gross = round(gross, 2)
    free  = round(free,  2)

    # PAX — sum quantities across all items
    pax = 0
    for item in items:
        for q in (item.get("quantities") or []):
            pax += int(q.get("value") or 0)
    if pax == 0:
        # fallback: try top-level field
        pax = int(b.get("totalParticipants") or b.get("numParticipants") or 1)

    return {
        "y": year, "d": d, "df": df,
        "net": net, "free": free, "gross": gross,
        "pax": pax, "prod": prod, "src": src,
    }


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    all_orders = []

    for w in FETCH_WINDOWS:
        print(f"\nFetching {w['year']}: {w['min']} → {w['max']}")
        bookings = fetch_bookings(w["min"], w["max"])
        print(f"Raw bookings returned: {len(bookings)}")

        parsed = 0
        for b in bookings:
            o = parse_booking(b, w["year"])
            if o:
                all_orders.append(o)
                parsed += 1
        print(f"Confirmed & parsed:    {parsed}")

        if bookings and parsed == 0:
            # Print first raw booking so we can inspect field names
            print("DEBUG first raw booking:")
            print(json.dumps(bookings[0], indent=2, default=str)[:800])

    print(f"\nTotal orders ready: {len(all_orders)}")

    # Sort: year desc, then date desc
    all_orders.sort(key=lambda o: (o["y"], o["d"]), reverse=True)

    # Build the JS array string
    entries = [
        (
            f'{{"y":{o["y"]},"d":"{o["d"]}","df":"{o["df"]}",'
            f'"net":{o["net"]},"free":{o["free"]},"gross":{o["gross"]},'
            f'"pax":{o["pax"]},"prod":"{o["prod"]}","src":"{o["src"]}"}}'
        )
        for o in all_orders
    ]
    js_arr = "var ORDERS = [" + ",".join(entries) + "];"

    # ── Patch the HTML file ───────────────────────────────────────────────────
    html_path = os.path.normpath(HTML_FILE)
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    start = html.index("var ORDERS = [")
    end   = html.index("];", start) + 2
    html  = html[:start] + js_arr + html[end:]

    # Update footer date stamp
    today = date.today().strftime("%d/%m/%Y")
    html  = re.sub(
        r"\d{2}/\d{2}/\d{4} &middot; Vertical Rio",
        f"{today} &middot; Vertical Rio",
        html,
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML updated: {html_path}")
    print(f"Footer date:  {today}")


if __name__ == "__main__":
    main()
