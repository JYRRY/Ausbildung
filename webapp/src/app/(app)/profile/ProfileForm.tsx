"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { Button, Label } from "@/components/ui";
import type { Me } from "@/lib/types";

interface FieldError {
  full_name?: string;
  app_password?: string;
}

export function ProfileForm({ me }: { me: Me }) {
  const router = useRouter();
  const initial = {
    full_name: me.full_name ?? "",
    app_password: "",
  };
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState<FieldError>({});
  const [busy, setBusy] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  const dirty =
    values.full_name !== initial.full_name || values.app_password.length > 0;

  function validate(): FieldError {
    const next: FieldError = {};
    if (!values.full_name.trim()) {
      next.full_name = "Pflichtfeld";
    }
    const pw = values.app_password.replace(/\s/g, "");
    if (!me.has_app_password && !pw) {
      next.app_password = "Pflichtfeld";
    } else if (pw && pw.length !== 16) {
      next.app_password = "App-Passwort muss genau 16 Zeichen lang sein.";
    }
    return next;
  }

  async function save() {
    const v = validate();
    setErrors(v);
    if (Object.keys(v).length > 0) {
      setMsg({ tone: "err", text: "Bitte fülle die markierten Pflichtfelder aus." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const profileRes = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: values.full_name.trim() }),
        credentials: "include",
      });
      if (!profileRes.ok) throw new Error(await profileRes.text());

      if (values.app_password.trim()) {
        const pwRes = await fetch("/api/profile/app-password", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ app_password: values.app_password }),
          credentials: "include",
        });
        if (!pwRes.ok) {
          const body = await pwRes.json().catch(() => ({}));
          throw new Error(body.detail || "Fehler beim Speichern des App-Passworts");
        }
      }

      setMsg({ tone: "ok", text: "✅ Profil gespeichert." });
      setValues((s) => ({ ...s, app_password: "" }));
      router.refresh();
    } catch (err) {
      setMsg({ tone: "err", text: `❌ ${(err as Error).message}` });
    } finally {
      setBusy(false);
    }
  }

  function cancel() {
    setValues(initial);
    setErrors({});
    setMsg(null);
  }

  return (
    <div className="space-y-5">
      {/* Sending email — read-only, pinned to the Google login account. */}
      <div>
        <Label>Gmail-Adresse (Versand)</Label>
        <div className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-sm text-slate-600 flex items-center justify-between">
          <span>{me.email ?? "—"}</span>
          <span className="text-xs text-slate-400">gesperrt</span>
        </div>
        <div className="text-xs text-slate-500 mt-1">
          Bewerbungen werden von deinem Anmelde-Konto versendet. Diese Adresse
          ist fest mit deinem Google-Login verknüpft und kann nicht geändert
          werden.
        </div>
      </div>

      <div>
        <Label htmlFor="full_name">
          Absendername<span className="text-red-500 ml-1">*</span>
        </Label>
        <input
          id="full_name"
          value={values.full_name}
          onChange={(e) =>
            setValues((s) => ({ ...s, full_name: e.target.value }))
          }
          placeholder="Vor- und Nachname"
          className={clsx(
            "w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500",
            errors.full_name ? "border-red-500 bg-red-50" : "border-slate-300",
          )}
        />
        {errors.full_name && (
          <div className="text-xs text-red-600 mt-1">{errors.full_name}</div>
        )}
      </div>

      <div>
        <Label htmlFor="app_password">
          Google App-Passwort
          {!me.has_app_password && <span className="text-red-500 ml-1">*</span>}
          {me.has_app_password && (
            <span className="text-xs text-slate-500 font-normal ml-2">
              (bereits gespeichert — nur ausfüllen, um zu ändern)
            </span>
          )}
        </Label>
        <input
          id="app_password"
          type="password"
          value={values.app_password}
          onChange={(e) =>
            setValues((s) => ({ ...s, app_password: e.target.value }))
          }
          placeholder={
            me.has_app_password ? "•••• •••• •••• ••••" : "abcd efgh ijkl mnop"
          }
          className={clsx(
            "w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500",
            errors.app_password ? "border-red-500 bg-red-50" : "border-slate-300",
          )}
        />
        {errors.app_password && (
          <div className="text-xs text-red-600 mt-1">{errors.app_password}</div>
        )}
        <button
          type="button"
          onClick={() => setShowHelp((v) => !v)}
          className="text-xs text-brand-600 underline mt-1.5"
        >
          {showHelp ? "Anleitung ausblenden" : "Wie erstelle ich ein App-Passwort?"}
        </button>
        {showHelp && <AppPasswordHelp />}
      </div>

      <div className="flex items-center gap-3 pt-3 border-t border-slate-200">
        <Button onClick={save} disabled={busy || !dirty}>
          {busy ? "Speichern…" : "Speichern"}
        </Button>
        <Button variant="ghost" onClick={cancel} disabled={busy || !dirty}>
          Abbrechen
        </Button>
        {msg && (
          <div
            className={clsx(
              "text-sm ml-2",
              msg.tone === "ok" ? "text-emerald-600" : "text-red-600",
            )}
          >
            {msg.text}
          </div>
        )}
      </div>
    </div>
  );
}

function AppPasswordHelp() {
  return (
    <div className="mt-3 p-4 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700 space-y-2">
      <p className="font-medium text-slate-900">
        App-Passwort in 4 Schritten erstellen:
      </p>
      <ol className="list-decimal list-inside space-y-1.5">
        <li>
          Aktiviere die{" "}
          <a
            className="text-brand-600 underline"
            href="https://myaccount.google.com/signinoptions/two-step-verification"
            target="_blank"
            rel="noopener"
          >
            Bestätigung in zwei Schritten (2FA)
          </a>{" "}
          — ohne 2FA gibt es keine App-Passwörter.
        </li>
        <li>
          Öffne{" "}
          <a
            className="text-brand-600 underline"
            href="https://myaccount.google.com/apppasswords"
            target="_blank"
            rel="noopener"
          >
            myaccount.google.com/apppasswords
          </a>
          .
        </li>
        <li>
          Gib einen Namen ein (z. B. <em>JYRY AI</em>) und klicke auf{" "}
          <strong>Erstellen</strong>.
        </li>
        <li>
          Google zeigt ein <strong>16-stelliges Passwort</strong> (in 4 Blöcken).
          Kopiere es und füge es oben ein — mit oder ohne Leerzeichen.
        </li>
      </ol>
      <p className="text-xs text-slate-500">
        Das Passwort wird verschlüsselt gespeichert und ausschließlich für den
        E-Mail-Versand über dein Gmail-Konto verwendet.
      </p>
    </div>
  );
}
