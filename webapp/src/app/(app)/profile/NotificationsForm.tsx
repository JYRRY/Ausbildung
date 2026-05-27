"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import type { NotificationMode } from "@/lib/types";

const OPTIONS: { value: NotificationMode; label: string; hint: string }[] = [
  {
    value: "per_send",
    label: "🔔 Pro Bewerbung",
    hint: "Nachricht im Telegram-Bot nach jeder gesendeten Bewerbung.",
  },
  {
    value: "daily",
    label: "📊 Tagesbericht",
    hint: "Eine Zusammenfassung am Ende des Tages.",
  },
  {
    value: "off",
    label: "🔕 Aus",
    hint: "Keine Benachrichtigungen.",
  },
];

export function NotificationsForm({ mode }: { mode: NotificationMode | null }) {
  const router = useRouter();
  const [current, setCurrent] = useState<NotificationMode>(mode ?? "off");
  const [busy, setBusy] = useState(false);

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
      {OPTIONS.map((opt) => (
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
