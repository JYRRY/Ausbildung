import { serverFetch } from "@/lib/api";
import { getLang } from "@/lib/lang";
import { translator } from "@/lib/i18n";
import type { Onboarding } from "@/lib/types";
import { SetupClient } from "./SetupClient";

export const metadata = { title: "Einrichtung — JYRY AI" };

export default async function SetupPage() {
  const lang = await getLang();
  const t = translator(lang);
  const data = await serverFetch<Onboarding>("/api/onboarding");

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t("setup.title")}</h1>
        <p className="text-slate-600 mt-1 text-sm">{t("setup.lead")}</p>
      </div>
      <SetupClient data={data} lang={lang} />
    </div>
  );
}
