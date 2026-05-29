"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard,
  Mail,
  User as UserIcon,
  CreditCard,
  Shield,
  LogOut,
} from "lucide-react";
import type { Me } from "@/lib/types";

const NAV = [
  { href: "/app", label: "Dashboard", icon: LayoutDashboard },
  { href: "/app/applications", label: "Bewerbungen", icon: Mail },
  { href: "/app/profile", label: "Profil", icon: UserIcon },
  { href: "/app/subscription", label: "Abo", icon: CreditCard },
];

export function Sidebar({ me }: { me: Me }) {
  const pathname = usePathname();
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white min-h-screen flex flex-col">
      <div className="p-5 border-b border-slate-200">
        <Link href="/app" className="font-semibold text-lg text-slate-900">
          JYRY AI
        </Link>
        <div className="text-xs text-slate-500 mt-1">Dashboard</div>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/app" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-700 hover:bg-slate-50",
              )}
            >
              <Icon size={16} />
              {item.label}
            </Link>
          );
        })}

        {me.is_admin && (
          <Link
            href="/app/admin"
            className={clsx(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors mt-4 border-t border-slate-200 pt-4",
              pathname.startsWith("/app/admin")
                ? "bg-amber-50 text-amber-700"
                : "text-slate-700 hover:bg-slate-50",
            )}
          >
            <Shield size={16} />
            Admin
          </Link>
        )}
      </nav>

      <div className="p-3 border-t border-slate-200 flex items-center gap-3">
        {me.google_picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={me.google_picture}
            alt=""
            className="w-9 h-9 rounded-full"
          />
        ) : (
          <div className="w-9 h-9 rounded-full bg-slate-200" />
        )}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-slate-900 truncate">
            {me.full_name ?? me.email}
          </div>
          <div className="text-xs text-slate-500 truncate">{me.email}</div>
        </div>
        <form action="/api/auth/logout" method="post">
          <button
            type="submit"
            className="text-slate-400 hover:text-red-600"
            title="Abmelden"
          >
            <LogOut size={16} />
          </button>
        </form>
      </div>
    </aside>
  );
}
