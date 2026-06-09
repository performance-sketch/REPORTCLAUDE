"use client";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { DailyMetaRow, DailyBookingRow } from "@/lib/types";

interface Props {
  metaDaily: DailyMetaRow[];
  bookingDaily: DailyBookingRow[];
}

export default function SpendRevenueChart({ metaDaily, bookingDaily }: Props) {
  const revenueByDate = Object.fromEntries(
    bookingDaily.map((r) => [r.date, r.gross_revenue])
  );

  const data = metaDaily.map((r) => ({
    date: r.date.slice(5),
    Investimento: r.spend,
    Receita: revenueByDate[r.date] ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })} />
        <Legend />
        <Bar dataKey="Investimento" fill="#6366f1" radius={[3, 3, 0, 0]} />
        <Line dataKey="Receita" type="monotone" stroke="#10b981" strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
