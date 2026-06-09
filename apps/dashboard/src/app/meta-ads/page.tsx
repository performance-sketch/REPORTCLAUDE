import { api, fmtBRL, fmtPct, fmt } from "@/lib/api";
import KpiCard from "@/components/cards/KpiCard";

export const revalidate = 60;

export default async function MetaAdsPage() {
  const data = await api.metaAds();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Meta Ads</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <KpiCard label="Investimento" value={fmtBRL(data.spend)} highlight />
        <KpiCard label="Impressões" value={fmt(data.impressions)} />
        <KpiCard label="Alcance" value={fmt(data.reach)} />
        <KpiCard label="Cliques" value={fmt(data.clicks)} />
        <KpiCard label="CTR" value={fmtPct(data.ctr)} />
        <KpiCard label="CPC" value={fmtBRL(data.cpc)} />
        <KpiCard label="CPM" value={fmtBRL(data.cpm)} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Link Clicks" value={fmt(data.link_clicks)} />
        <KpiCard label="Landing Page Views" value={fmt(data.landing_page_views)} />
        <KpiCard label="Leads" value={fmt(data.leads)} />
        <KpiCard label="Compras" value={fmt(data.purchases)} />
        <KpiCard label="Valor de Conv." value={fmtBRL(data.conversion_value)} />
        <KpiCard label="CPA" value={fmtBRL(data.cpa)} />
        <KpiCard label="ROAS Meta" value={data.roas_meta != null ? `${data.roas_meta.toFixed(2)}×` : "—"} />
        <KpiCard label="Frequência" value={data.frequency != null ? data.frequency.toFixed(2) : "—"} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-semibold mb-3">Performance por Campanha</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[800px]">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Campanha</th>
                <th className="pb-2 text-right">Gasto</th>
                <th className="pb-2 text-right">Impressões</th>
                <th className="pb-2 text-right">Cliques</th>
                <th className="pb-2 text-right">CTR</th>
                <th className="pb-2 text-right">CPC</th>
                <th className="pb-2 text-right">CPM</th>
                <th className="pb-2 text-right">Leads</th>
                <th className="pb-2 text-right">Compras</th>
                <th className="pb-2 text-right">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {data.campaigns.map((c, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 max-w-[220px] truncate font-medium">{c.campaign_name ?? "—"}</td>
                  <td className="py-2 text-right">{fmtBRL(c.spend)}</td>
                  <td className="py-2 text-right">{fmt(c.impressions)}</td>
                  <td className="py-2 text-right">{fmt(c.clicks)}</td>
                  <td className="py-2 text-right">{fmtPct(c.ctr)}</td>
                  <td className="py-2 text-right">{fmtBRL(c.cpc)}</td>
                  <td className="py-2 text-right">{fmtBRL(c.cpm)}</td>
                  <td className="py-2 text-right">{fmt(c.leads)}</td>
                  <td className="py-2 text-right">{fmt(c.purchases)}</td>
                  <td className="py-2 text-right">{c.roas != null ? `${c.roas.toFixed(2)}×` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
