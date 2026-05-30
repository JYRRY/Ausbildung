"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui";
import { translator, type Lang } from "@/lib/i18n";

export function ActiveToggle({
  isActive,
  lang = "de",
}: {
  isActive: boolean;
  lang?: Lang;
}) {
  const router = useRouter();
  const t = translator(lang);
  const [active, setActive] = useState(isActive);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    const next = !active;
    try {
      await fetch("/api/active", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: next }),
        credentials: "include",
      });
      setActive(next);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="font-medium text-slate-900 text-sm">
          {active ? t("versand.running") : t("versand.paused")}
        </div>
        <div className="text-xs text-slate-500 mt-0.5">
          {active ? t("versand.running_hint") : t("versand.paused_hint")}
        </div>
      </div>
      <Button variant={active ? "ghost" : "primary"} onClick={toggle} disabled={busy}>
        {active ? t("versand.pause") : t("versand.resume")}
      </Button>
    </div>
  );
}
