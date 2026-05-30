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
import type { Lang } from "@/lib/i18n";
import { translator } from "@/lib/i18n";
import { LanguageToggle } from "./LanguageToggle";

export function Sidebar({ me, lang }: { me: Me; lang: Lang }) {
  const pathname = usePathname();
  const t = translator(lang);

  const nav = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/applications", label: t("nav.applications"), icon: Mail },
    { href: "/profile", label: t("nav.profile"), icon: UserIcon },
    { href: "/subscription", label: t("nav.subscription"), icon: CreditCard },
  ];

  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white h-screen sticky top-0 flex flex-col">
      <div className="p-5 border-b border-slate-200 flex items-center justify-between">
        <div>
          <Link href="/dashboard" className="font-semibold text-lg text-slate-900">
            JYRY AI
          </Link>
          <div className="text-xs text-slate-500 mt-1">{t("nav.subtitle")}</div>
        </div>
        <LanguageToggle current={lang} />
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {nav.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
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
            href="/admin"
            className={clsx(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors mt-4 border-t border-slate-200 pt-4",
              pathname.startsWith("/admin")
                ? "bg-amber-50 text-amber-700"
                : "text-slate-700 hover:bg-slate-50",
            )}
          >
            <Shield size={16} />
            {t("nav.admin")}
          </Link>
        )}
      </nav>

      <div className="p-3 border-t border-slate-200 flex items-center gap-3">
        {me.google_picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={me.google_picture} alt="" className="w-9 h-9 rounded-full" />
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
            title={t("action.logout")}
          >
            <LogOut size={16} />
          </button>
        </form>
      </div>
    </aside>
  );
}
