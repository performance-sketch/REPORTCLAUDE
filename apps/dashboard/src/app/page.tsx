import { api, fmtBRL, fmtPct, fmt } from "@/lib/api";
import KpiCard from "@/components/cards/KpiCard";
import SpendRevenueChart from "@/components/charts/SpendRevenueChart";
import FunnelChart from "@/components/charts/FunnelChart";

export const revalidate = 60;

export default async function OverviewPage() {
  const data = await api.overview();

  const funnelSteps = [
    { label: "Impressões", value: data.impressions ?? 0 },
    { label: "Cliques", value: data.clicks ?? 0, rate: fmtPct(data.ctr) },
    { label: "Reservas Criadas", value: data.bookings_created, rate: fmtPct(data.click_to_booking_rate) },
    { label: "Reservas Confirmadas", value: data.bookings_confirmed },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard label="Investimento" value={fmtBRL(data.meta_spend)} highlight />
        <KpiCard label="Receita Confirmada" value={fmtBRL(data.confirmed_revenue)} highlight />
        <KpiCard label="ROAS Real" value={data.roas_real != null ? `${data.roas_real.toFixed(2)}×` : "—"} />
        <KpiCard label="Reservas Conf." value={fmt(data.bookings_confirmed)} sub={`CAC ${fmtBRL(data.cac)}`} />
        <KpiCard label="Ticket Médio" value={fmtBRL(data.avg_ticket)} />
        <KpiCard label="Taxa Cancelam." value={fmtPct(data.cancellation_rate)} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Cliques" value={fmt(data.clicks)} />
        <KpiCard label="CTR" value={fmtPct(data.ctr)} />
        <KpiCard label="CPC" value={fmtBRL(data.cpc)} />
        <KpiCard label="CPM" value={fmtBRL(data.cpm)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Investimento vs Receita (diário)</h2>
          <SpendRevenueChart metaDaily={data.daily_meta} bookingDaily={data.daily_bookings} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Funil de Aquisição</h2>
          <FunnelChart steps={funnelSteps} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Top Campanhas</h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Campanha</th>
                <th className="pb-2 text-right">Gasto</th>
                <th className="pb-2 text-right">CTR</th>
                <th className="pb-2 text-right">ROAS</th>
              </tr>
            </thead>
            <tbody>
              {data.top_campaigns.map((c, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5 max-w-[160px] truncate">{c.campaign_name ?? "—"}</td>
                  <td className="py-1.5 text-right">{fmtBRL(c.spend)}</td>
                  <td className="py-1.5 text-right">{fmtPct(c.ctr)}</td>
                  <td className="py-1.5 text-right">{c.roas != null ? `${c.roas.toFixed(2)}×` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Top Produtos</h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Produto</th>
                <th className="pb-2 text-right">Reservas</th>
                <th className="pb-2 text-right">Receita</th>
                <th className="pb-2 text-right">Ticket</th>
              </tr>
            </thead>
            <tbody>
              {data.top_products.map((p, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5 max-w-[160px] truncate">{p.product_name ?? "—"}</td>
                  <td className="py-1.5 text-right">{p.bookings_confirmed}</td>
                  <td className="py-1.5 text-right">{fmtBRL(p.revenue)}</td>
                  <td className="py-1.5 text-right">{fmtBRL(p.avg_ticket)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
