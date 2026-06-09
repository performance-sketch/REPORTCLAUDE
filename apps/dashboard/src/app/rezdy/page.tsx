import { api, fmtBRL, fmtPct, fmt } from "@/lib/api";
import KpiCard from "@/components/cards/KpiCard";

export const revalidate = 60;

export default async function RezdyPage() {
  const data = await api.bookings();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Rezdy — Reservas</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <KpiCard label="Criadas" value={fmt(data.bookings_created)} />
        <KpiCard label="Confirmadas" value={fmt(data.bookings_confirmed)} highlight />
        <KpiCard label="Canceladas" value={fmt(data.bookings_cancelled)} />
        <KpiCard label="Taxa Cancelam." value={fmtPct(data.cancellation_rate)} />
        <KpiCard label="Receita Bruta" value={fmtBRL(data.gross_revenue)} highlight />
        <KpiCard label="Ticket Médio" value={fmtBRL(data.avg_ticket)} />
        <KpiCard label="Total PAX" value={fmt(data.total_pax)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Por Status</h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Status</th>
                <th className="pb-2 text-right">Qtd</th>
                <th className="pb-2 text-right">Receita</th>
              </tr>
            </thead>
            <tbody>
              {data.by_status.map((s, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5">{s.order_status ?? "—"}</td>
                  <td className="py-1.5 text-right">{fmt(s.count)}</td>
                  <td className="py-1.5 text-right">{fmtBRL(s.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h2 className="text-sm font-semibold mb-3">Receita por Produto</h2>
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
              {data.by_product.map((p, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5 max-w-[150px] truncate">{p.product_name ?? "—"}</td>
                  <td className="py-1.5 text-right">{p.bookings_confirmed}</td>
                  <td className="py-1.5 text-right">{fmtBRL(p.revenue)}</td>
                  <td className="py-1.5 text-right">{fmtBRL(p.avg_ticket)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-semibold mb-3">Reservas por Dia</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[600px]">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Data</th>
                <th className="pb-2 text-right">Criadas</th>
                <th className="pb-2 text-right">Confirmadas</th>
                <th className="pb-2 text-right">Canceladas</th>
                <th className="pb-2 text-right">Receita</th>
              </tr>
            </thead>
            <tbody>
              {data.daily.map((d, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-1.5">{d.date}</td>
                  <td className="py-1.5 text-right">{d.bookings_created}</td>
                  <td className="py-1.5 text-right">{d.bookings_confirmed}</td>
                  <td className="py-1.5 text-right">{d.bookings_cancelled}</td>
                  <td className="py-1.5 text-right">{fmtBRL(d.gross_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
