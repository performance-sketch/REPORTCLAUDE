"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const nav = [
  { href: "/", label: "Overview" },
  { href: "/meta-ads", label: "Meta Ads" },
  { href: "/rezdy", label: "Rezdy" },
  { href: "/funnel", label: "Funil" },
  { href: "/health", label: "Data Health" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-52 bg-white border-r flex flex-col py-6 px-3 shrink-0">
      <p className="text-xs font-bold uppercase text-gray-400 px-3 mb-4 tracking-widest">Dashboard</p>
      <nav className="flex flex-col gap-1">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              "px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              path === item.href
                ? "bg-indigo-50 text-indigo-700"
                : "text-gray-600 hover:bg-gray-100"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
