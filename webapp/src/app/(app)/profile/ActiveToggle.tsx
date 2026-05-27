"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui";

export function ActiveToggle({ isActive }: { isActive: boolean }) {
  const router = useRouter();
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
          {active ? "Versand läuft" : "Versand pausiert"}
        </div>
        <div className="text-xs text-slate-500 mt-0.5">
          {active
            ? "Bewerbungen werden über den Tag verteilt verschickt."
            : "Der Versand ist gestoppt. Schalte ihn wieder ein, um fortzusetzen."}
        </div>
      </div>
      <Button variant={active ? "ghost" : "primary"} onClick={toggle} disabled={busy}>
        {active ? "Pausieren" : "Fortsetzen"}
      </Button>
    </div>
  );
}
