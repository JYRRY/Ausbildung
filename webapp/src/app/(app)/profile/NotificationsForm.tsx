"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import type { NotificationMode } from "@/lib/types";
import { translator, type Lang } from "@/lib/i18n";

export function NotificationsForm({
  mode,
  lang = "de",
}: {
  mode: NotificationMode | null;
  lang?: Lang;
}) {
  const router = useRouter();
  const t = translator(lang);
  const [current, setCurrent] = useState<NotificationMode>(mode ?? "off");
  const [busy, setBusy] = useState(false);

  const options: { value: NotificationMode; label: string; hint: string }[] = [
    { value: "per_send", label: t("notif.per_send"), hint: t("notif.per_send_hint") },
    { value: "daily", label: t("notif.daily"), hint: t("notif.daily_hint") },
    { value: "off", label: t("notif.off"), hint: t("notif.off_hint") },
  ];

  async function pick(value: NotificationMode) {
    setBusy(true);
    setCurrent(value);
    try {
      await fetch("/api/notifications", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: value }),
        credentials: "include",
      });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => pick(opt.value)}
          disabled={busy}
          className={clsx(
            "w-full text-left p-3 rounded-lg border transition-colors",
            current === opt.value
              ? "border-brand-500 bg-brand-50"
              : "border-slate-200 hover:bg-slate-50",
          )}
        >
          <div className="font-medium text-slate-900 text-sm">{opt.label}</div>
          <div className="text-xs text-slate-500 mt-0.5">{opt.hint}</div>
        </button>
      ))}
    </div>
  );
}
