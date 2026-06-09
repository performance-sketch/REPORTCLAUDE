import { api, fmtBRL, fmtPct, fmt } from "@/lib/api";
import KpiCard from "@/components/cards/KpiCard";
import FunnelChart from "@/components/charts/FunnelChart";

export const revalidate = 60;

export default async function FunnelPage() {
  const data = await api.funnel();

  const steps = [
    { label: "Impressões", value: data.impressions },
    { label: "Cliques", value: data.clicks, rate: fmtPct(data.imp_to_click_rate) },
    { label: "LPV", value: data.landing_page_views },
    { label: "Reservas Criadas", value: data.bookings_created, rate: fmtPct(data.click_to_booking_rate) },
    { label: "Reservas Confirmadas", value: data.bookings_confirmed, rate: fmtPct(data.booking_to_confirmed_rate) },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Funil Integrado</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="ROAS Real" value={data.roas_real != null ? `${data.roas_real.toFixed(2)}×` : "—"} highlight />
        <KpiCard label="Custo / Reserva Criada" value={fmtBRL(data.cost_per_booking_created)} />
        <KpiCard label="Custo / Reserva Conf." value={fmtBRL(data.cost_per_booking_confirmed)} />
        <KpiCard label="Receita / Clique" value={fmtBRL(data.revenue_per_click)} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-semibold mb-4">Funil Completo</h2>
        <FunnelChart steps={steps} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-semibold mb-3">ROAS Real por Campanha</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[700px]">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Campanha</th>
                <th className="pb-2 text-right">Gasto</th>
                <th className="pb-2 text-right">Cliques</th>
                <th className="pb-2 text-right">CTR</th>
                <th className="pb-2 text-right">Receita Conf.</th>
                <th className="pb-2 text-right">ROAS Meta</th>
                <th className="pb-2 text-right">CPC</th>
              </tr>
            </thead>
            <tbody>
              {data.by_campaign.map((c, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 max-w-[200px] truncate font-medium">{c.campaign_name ?? "—"}</td>
                  <td className="py-2 text-right">{fmtBRL(c.spend)}</td>
                  <td className="py-2 text-right">{fmt(c.clicks)}</td>
                  <td className="py-2 text-right">{fmtPct(c.ctr)}</td>
                  <td className="py-2 text-right">{fmtBRL(c.conversion_value)}</td>
                  <td className="py-2 text-right">{c.roas != null ? `${c.roas.toFixed(2)}×` : "—"}</td>
                  <td className="py-2 text-right">{fmtBRL(c.cpc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
