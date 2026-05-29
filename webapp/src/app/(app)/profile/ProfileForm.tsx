"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { Button, Label } from "@/components/ui";
import type { Me } from "@/lib/types";

interface FieldError {
  full_name?: string;
  gmail_address?: string;
  app_password?: string;
}

export function ProfileForm({ me }: { me: Me }) {
  const router = useRouter();
  const initial = {
    full_name: me.full_name ?? "",
    gmail_address: me.gmail_address ?? "",
    app_password: "",
  };
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState<FieldError>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  const dirty =
    values.full_name !== initial.full_name ||
    values.gmail_address !== initial.gmail_address ||
    values.app_password.length > 0;

  function validate(): FieldError {
    const next: FieldError = {};
    if (!values.full_name.trim()) {
      next.full_name = "Pflichtfeld";
    }
    if (!values.gmail_address.trim()) {
      next.gmail_address = "Pflichtfeld";
    } else if (
      !values.gmail_address.includes("@") ||
      !values.gmail_address.split("@")[1]?.includes(".")
    ) {
      next.gmail_address = "Ungültige E-Mail-Adresse";
    }
    // App password only required if not already stored AND not provided.
    if (!me.has_app_password && !values.app_password.trim()) {
      next.app_password = "Pflichtfeld";
    } else if (
      values.app_password.trim() &&
      values.app_password.replace(/\s/g, "").length < 12
    ) {
      next.app_password = "Mindestens 12 Zeichen";
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
        body: JSON.stringify({
          full_name: values.full_name.trim(),
          gmail_address: values.gmail_address.trim(),
        }),
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
        if (!pwRes.ok) throw new Error(await pwRes.text());
      }

      setMsg({ tone: "ok", text: "✅ Profil gespeichert." });
      setValues((v) => ({ ...v, app_password: "" }));
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
      <Field
        id="full_name"
        label="Absendername"
        required
        error={errors.full_name}
        value={values.full_name}
        onChange={(v) => setValues((s) => ({ ...s, full_name: v }))}
        placeholder="Vor- und Nachname"
      />

      <Field
        id="gmail"
        label="Gmail-Adresse (für den Versand)"
        required
        error={errors.gmail_address}
        value={values.gmail_address}
        onChange={(v) =>
          setValues((s) => ({ ...s, gmail_address: v.toLowerCase() }))
        }
        type="email"
        placeholder="name@gmail.com"
        hint="Dies ist die Adresse, von der die Bewerbungen versendet werden — kann eine andere sein als die zur Anmeldung verwendete."
      />

      <Field
        id="app_password"
        label={
          <>
            Google App-Passwort
            {me.has_app_password && (
              <span className="text-xs text-slate-500 font-normal ml-2">
                (bereits gespeichert — nur ausfüllen, um zu ändern)
              </span>
            )}
          </>
        }
        required={!me.has_app_password}
        error={errors.app_password}
        value={values.app_password}
        onChange={(v) => setValues((s) => ({ ...s, app_password: v }))}
        type="password"
        placeholder={
          me.has_app_password ? "•••• •••• •••• ••••" : "abcd efgh ijkl mnop"
        }
        hint={
          <>
            Erstellen unter{" "}
            <a
              className="underline"
              href="https://myaccount.google.com/apppasswords"
              target="_blank"
              rel="noopener"
            >
              myaccount.google.com/apppasswords
            </a>{" "}
            — 2-Faktor-Authentifizierung muss aktiv sein.
          </>
        }
      />

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

type FieldProps = {
  id: string;
  label: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  error?: string;
  type?: string;
  placeholder?: string;
  hint?: React.ReactNode;
};

function Field({
  id,
  label,
  value,
  onChange,
  required,
  error,
  type = "text",
  placeholder,
  hint,
}: FieldProps) {
  return (
    <div>
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </Label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={clsx(
          "w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500",
          error
            ? "border-red-500 bg-red-50"
            : "border-slate-300",
        )}
      />
      {error ? (
        <div className="text-xs text-red-600 mt-1">{error}</div>
      ) : hint ? (
        <div className="text-xs text-slate-500 mt-1">{hint}</div>
      ) : null}
    </div>
  );
}
