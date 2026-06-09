interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}

export default function KpiCard({ label, value, sub, highlight }: KpiCardProps) {
  return (
    <div className={`rounded-xl border p-4 bg-white shadow-sm ${highlight ? "border-indigo-300" : "border-gray-200"}`}>
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? "text-indigo-700" : "text-gray-900"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}
