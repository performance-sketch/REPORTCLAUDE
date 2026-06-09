import { api, fmt } from "@/lib/api";
import KpiCard from "@/components/cards/KpiCard";

export const revalidate = 30;

function statusColor(s: string) {
  if (s === "success") return "text-green-600";
  if (s === "error") return "text-red-600";
  if (s === "running") return "text-yellow-600";
  return "text-gray-600";
}

export default async function HealthPage() {
  const data = await api.syncHealth();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Data Health</h1>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <KpiCard
          label="Eventos Pendentes"
          value={fmt(data.pending_events)}
          sub="raw_events aguardando transform"
        />
        <KpiCard
          label="Eventos com Erro"
          value={fmt(data.error_events)}
          highlight={data.error_events > 0}
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="text-sm font-semibold mb-3">Syncs Recentes</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[700px]">
            <thead>
              <tr className="text-left text-gray-400 border-b">
                <th className="pb-2">Fonte</th>
                <th className="pb-2">Tipo</th>
                <th className="pb-2">Início</th>
                <th className="pb-2">Fim</th>
                <th className="pb-2">Status</th>
                <th className="pb-2 text-right">Processados</th>
                <th className="pb-2 text-right">Erros</th>
                <th className="pb-2">Mensagem</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_syncs.map((s, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 font-medium">{s.source}</td>
                  <td className="py-2 text-gray-500">{s.sync_type}</td>
                  <td className="py-2">{new Date(s.started_at).toLocaleString("pt-BR")}</td>
                  <td className="py-2">{s.finished_at ? new Date(s.finished_at).toLocaleString("pt-BR") : "—"}</td>
                  <td className={`py-2 font-semibold ${statusColor(s.status)}`}>{s.status}</td>
                  <td className="py-2 text-right">{fmt(s.records_processed)}</td>
                  <td className="py-2 text-right text-red-500">{s.records_failed || "—"}</td>
                  <td className="py-2 text-gray-400 max-w-[200px] truncate">{s.error_message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
