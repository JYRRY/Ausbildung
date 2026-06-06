"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { Trash2, Upload } from "lucide-react";
import { Button, Card, Label } from "@/components/ui";
import { translator, type Lang } from "@/lib/i18n";
import type { Onboarding } from "@/lib/types";

type Msg = { tone: "ok" | "err"; text: string } | null;

export function SetupClient({ data, lang }: { data: Onboarding; lang: Lang }) {
  const t = translator(lang);
  const router = useRouter();

  const [specialties, setSpecialties] = useState<string[]>(data.specialties);
  const [states, setStates] = useState<string[]>(data.states);
  const [subject, setSubject] = useState(data.subject_template);
  const [body, setBody] = useState(data.body_template);
  const [attachments, setAttachments] = useState(data.attachments);
  const [complete, setComplete] = useState(data.onboarding_complete);
  const [hasAppPw] = useState(data.has_app_password);

  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);

  async function refetch() {
    const res = await fetch("/api/onboarding", { credentials: "include" });
    if (!res.ok) return;
    const fresh: Onboarding = await res.json();
    setSpecialties(fresh.specialties);
    setStates(fresh.states);
    setSubject(fresh.subject_template);
    setBody(fresh.body_template);
    setAttachments(fresh.attachments);
    setComplete(fresh.onboarding_complete);
    router.refresh();
  }

  function toggle(
    list: string[],
    setList: (v: string[]) => void,
    value: string,
    max: number | null,
  ) {
    setMsg(null);
    if (list.includes(value)) {
      setList(list.filter((x) => x !== value));
      return;
    }
    if (max !== null && list.length >= max) {
      setMsg({ tone: "err", text: t("setup.limit_reached", { n: max }) });
      return;
    }
    setList([...list, value]);
  }

  async function call(
    key: string,
    path: string,
    init: RequestInit,
    okText?: string,
  ) {
    setBusy(key);
    setMsg(null);
    try {
      const res = await fetch(path, { credentials: "include", ...init });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      await refetch();
      if (okText) setMsg({ tone: "ok", text: okText });
      return true;
    } catch (err) {
      setMsg({ tone: "err", text: `❌ ${(err as Error).message}` });
      return false;
    } finally {
      setBusy(null);
    }
  }

  const saveSelection = () =>
    call(
      "selection",
      "/api/onboarding/selection",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specialties, states }),
      },
      t("profile.saved"),
    );

  const saveTemplate = () =>
    call(
      "template",
      "/api/onboarding/template",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject_template: subject, body_template: body }),
      },
      t("profile.saved"),
    );

  async function upload(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    await call("upload", "/api/onboarding/attachments", {
      method: "POST",
      body: fd,
    });
  }

  const remove = (index: number) =>
    call("del" + index, `/api/onboarding/attachments/${index}`, {
      method: "DELETE",
    });

  const finish = () =>
    call("complete", "/api/onboarding/complete", { method: "POST" }, t("setup.completed"));

  // Readiness (mirrors the backend _is_ready).
  const missing: string[] = [];
  if (!hasAppPw) missing.push(t("setup.miss_app_password"));
  if (specialties.length === 0) missing.push(t("setup.miss_specialties"));
  if (states.length === 0) missing.push(t("setup.miss_states"));
  if (!subject.trim()) missing.push(t("setup.miss_template"));
  const ready = missing.length === 0;

  function limitHint(count: number, max: number | null) {
    if (max === null) return t("setup.limit_unlimited");
    return t("setup.limit_count", { c: count, n: max });
  }

  return (
    <div className="space-y-6">
      {msg && (
        <div
          className={clsx(
            "text-sm px-4 py-2 rounded-lg",
            msg.tone === "ok"
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-700",
          )}
        >
          {msg.text}
        </div>
      )}

      {/* Specialties */}
      <Card title={t("setup.specialties_title")}>
        <p className="text-sm text-slate-600 mb-3">{t("setup.specialties_hint")}</p>
        <div className="flex flex-wrap gap-2">
          {data.all_specialties.map((s) => {
            const on = specialties.includes(s.keyword);
            return (
              <button
                key={s.keyword}
                type="button"
                onClick={() =>
                  toggle(specialties, setSpecialties, s.keyword, data.max_specialties)
                }
                className={chipClass(on)}
              >
                {s.label_de}
              </button>
            );
          })}
        </div>
        <div className="text-xs text-slate-500 mt-3">
          {limitHint(specialties.length, data.max_specialties)}
        </div>
      </Card>

      {/* States */}
      <Card title={t("setup.states_title")}>
        <p className="text-sm text-slate-600 mb-3">{t("setup.states_hint")}</p>
        <div className="flex flex-wrap gap-2">
          {data.all_states.map((s) => {
            const on = states.includes(s.code);
            return (
              <button
                key={s.code}
                type="button"
                onClick={() => toggle(states, setStates, s.code, data.max_states)}
                className={chipClass(on)}
              >
                {s.label_de}
              </button>
            );
          })}
        </div>
        <div className="text-xs text-slate-500 mt-3">
          {limitHint(states.length, data.max_states)}
        </div>
        <div className="pt-4 mt-4 border-t border-slate-200">
          <Button onClick={saveSelection} disabled={busy === "selection"}>
            {busy === "selection" ? t("action.saving") : t("action.save")}
          </Button>
        </div>
      </Card>

      {/* Template */}
      <Card title={t("setup.template_title")}>
        <p className="text-sm text-slate-600 mb-3">{t("setup.template_hint")}</p>
        <div className="space-y-4">
          <div>
            <Label htmlFor="subject">{t("setup.subject_label")}</Label>
            <input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </div>
          <div>
            <Label htmlFor="body">{t("setup.body_label")}</Label>
            <textarea
              id="body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 font-mono"
            />
          </div>
          <Button onClick={saveTemplate} disabled={busy === "template"}>
            {busy === "template" ? t("action.saving") : t("action.save")}
          </Button>
        </div>
      </Card>

      {/* Attachments */}
      <Card title={t("setup.attachments_title")}>
        <p className="text-sm text-slate-600 mb-3">{t("setup.attachments_hint")}</p>
        {attachments.length === 0 ? (
          <div className="text-sm text-slate-500">{t("setup.attachments_empty")}</div>
        ) : (
          <ul className="space-y-2">
            {attachments.map((a) => (
              <li
                key={a.index}
                className="flex items-center justify-between px-3 py-2 rounded-lg border border-slate-200 bg-slate-50"
              >
                <div className="min-w-0">
                  <span className="text-sm text-slate-800 truncate">{a.filename}</span>
                  <span className="text-xs text-slate-400 ml-2">
                    {(a.size / 1024).toFixed(0)} KB
                    {a.source === "telegram" && ` · ${t("setup.attachments_from_bot")}`}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => remove(a.index)}
                  disabled={busy === "del" + a.index}
                  className="text-slate-400 hover:text-red-600 shrink-0"
                  title={t("setup.delete")}
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg text-sm font-medium bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 cursor-pointer">
          <Upload size={16} />
          {busy === "upload"
            ? t("setup.attachments_uploading")
            : t("setup.attachments_upload")}
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            disabled={busy === "upload"}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              e.target.value = "";
            }}
          />
        </label>
      </Card>

      {/* Readiness / complete */}
      <Card title={t("setup.ready_title")}>
        {ready ? (
          <div className="text-sm text-emerald-700">{t("setup.ready_done")}</div>
        ) : (
          <div className="text-sm text-amber-700">
            {t("setup.ready_missing", { items: missing.join("، ") })}
          </div>
        )}
        {!complete && (
          <div className="pt-4 mt-4 border-t border-slate-200">
            <Button onClick={finish} disabled={!ready || busy === "complete"}>
              {busy === "complete" ? t("action.saving") : t("setup.complete_btn")}
            </Button>
          </div>
        )}
        {complete && (
          <div className="text-xs text-slate-500 mt-2">{t("setup.completed")}</div>
        )}
      </Card>
    </div>
  );
}

function chipClass(on: boolean) {
  return clsx(
    "px-3 py-1.5 rounded-full text-sm font-medium border transition-colors",
    on
      ? "bg-brand-600 text-white border-brand-600"
      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
  );
}
