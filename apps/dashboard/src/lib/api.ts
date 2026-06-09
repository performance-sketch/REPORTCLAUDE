import type { BookingsKPI, FunnelKPI, MetaAdsKPI, OverviewKPI, SyncHealth } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildUrl(path: string, params: Record<string, string | undefined> = {}): string {
  const url = new URL(`${BASE}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) url.searchParams.set(k, v);
  });
  return url.toString();
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API error ${res.status} ${url}`);
  return res.json() as Promise<T>;
}

export interface DateRange {
  dateStart?: string;
  dateEnd?: string;
}

export const api = {
  overview: (range?: DateRange) =>
    fetchJson<OverviewKPI>(buildUrl("/kpis/overview", {
      date_start: range?.dateStart,
      date_end: range?.dateEnd,
    })),

  metaAds: (range?: DateRange, accountId?: string, campaignId?: string) =>
    fetchJson<MetaAdsKPI>(buildUrl("/kpis/meta-ads", {
      date_start: range?.dateStart,
      date_end: range?.dateEnd,
      account_id: accountId,
      campaign_id: campaignId,
    })),

  bookings: (range?: DateRange, productCode?: string) =>
    fetchJson<BookingsKPI>(buildUrl("/kpis/bookings", {
      date_start: range?.dateStart,
      date_end: range?.dateEnd,
      product_code: productCode,
    })),

  funnel: (range?: DateRange, campaignId?: string) =>
    fetchJson<FunnelKPI>(buildUrl("/kpis/funnel", {
      date_start: range?.dateStart,
      date_end: range?.dateEnd,
      campaign_id: campaignId,
    })),

  syncHealth: () => fetchJson<SyncHealth>(buildUrl("/kpis/sync-health")),
};

export function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function fmtBRL(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(2)}%`;
}
