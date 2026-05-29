"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Input, Label } from "@/components/ui";
import type { Me } from "@/lib/types";

export function ProfileForm({ me }: { me: Me }) {
  const router = useRouter();
  const [fullName, setFullName] = useState(me.full_name ?? "");
  const [gmail, setGmail] = useState(me.gmail_address ?? "");
  const [appPassword, setAppPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const profileRes = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim() || null,
          gmail_address: gmail.trim() || null,
        }),
        credentials: "include",
      });
      if (!profileRes.ok) throw new Error(await profileRes.text());

      if (appPassword.trim()) {
        const pwRes = await fetch("/api/profile/app-password", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_password: appPassword }),
          credentials: "include",
        });
        if (!pwRes.ok) throw new Error(await pwRes.text());
        setAppPassword("");
      }

      setMsg("✅ Gespeichert");
      router.refresh();
    } catch (err) {
      setMsg(`❌ ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="full_name">Absendername</Label>
        <Input
          id="full_name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Vor- und Nachname"
        />
      </div>
      <div>
        <Label htmlFor="gmail">Gmail-Adresse (für den Versand)</Label>
        <Input
          id="gmail"
          type="email"
          value={gmail}
          onChange={(e) => setGmail(e.target.value)}
          placeholder="name@gmail.com"
        />
        <div className="text-xs text-slate-500 mt-1">
          Dies ist die Adresse, von der die Bewerbungen versendet werden — kann
          eine andere sein als die zur Anmeldung verwendete.
        </div>
      </div>
      <div>
        <Label htmlFor="app_password">
          Google App-Passwort{" "}
          {me.has_app_password && (
            <span className="text-xs text-slate-500">
              (bereits gespeichert — nur ausfüllen, um zu ändern)
            </span>
          )}
        </Label>
        <Input
          id="app_password"
          type="password"
          value={appPassword}
          onChange={(e) => setAppPassword(e.target.value)}
          placeholder={me.has_app_password ? "•••• •••• •••• ••••" : "abcd efgh ijkl mnop"}
        />
        <div className="text-xs text-slate-500 mt-1">
          Erstellen unter{" "}
          <a
            className="underline"
            href="https://myaccount.google.com/apppasswords"
            target="_blank"
            rel="noopener"
          >
            myaccount.google.com/apppasswords
          </a>
          {" "}— 2-Faktor-Authentifizierung muss aktiv sein.
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Button onClick={save} disabled={busy}>
          {busy ? "Speichern…" : "Speichern"}
        </Button>
        {msg && <div className="text-sm">{msg}</div>}
      </div>
    </div>
  );
}
