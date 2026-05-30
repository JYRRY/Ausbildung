import { Check, ChevronRight } from "lucide-react";
import clsx from "clsx";
import { serverFetch } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui";
import { getT } from "@/lib/lang";
import type { Me, Plan } from "@/lib/types";

export const metadata = { title: "Abo — JYRY AI" };

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  plus: "Plus",
  pro: "Pro",
  max: "Max",
};

const PLAN_RANK: Record<string, number> = { free: 0, plus: 1, pro: 2, max: 3 };

interface PlanRow {
  id: Plan;
  name: string;
  price: string;
  periodKey: string;
  emails: number;
  featureKeys: string[];
  upgradable: boolean;
}

const PLAN_ROWS: PlanRow[] = [
  {
    id: "free",
    name: "Free",
    price: "0 €",
    periodKey: "sub.free_period",
    emails: 10,
    featureKeys: ["sub.f_1beruf", "sub.f_1land"],
    upgradable: false,
  },
  {
    id: "plus",
    name: "Plus",
    price: "14,99 €",
    periodKey: "sub.plus_period",
    emails: 30,
    featureKeys: ["sub.f_3berufe", "sub.f_6laender"],
    upgradable: true,
  },
  {
    id: "pro",
    name: "Pro",
    price: "29,99 €",
    periodKey: "sub.pro_period",
    emails: 100,
    featureKeys: ["sub.f_allberufe", "sub.f_alllaender", "sub.f_templates"],
    upgradable: true,
  },
  {
    id: "max",
    name: "Max",
    price: "69,99 €",
    periodKey: "sub.max_period",
    emails: 200,
    featureKeys: [
      "sub.f_allberufe",
      "sub.f_alllaender",
      "sub.f_templates",
      "sub.f_support",
    ],
    upgradable: true,
  },
];

export default async function SubscriptionPage() {
  const { lang, t } = await getT();
  const me = await serverFetch<Me>("/api/me");
  const sub = me.subscription;
  const currentPlan = (sub?.plan ?? "free") as Plan;
  const currentRank = PLAN_RANK[currentPlan];
  const locale = lang === "de" ? "de-DE" : "en-GB";
  const expiresLabel = sub?.expires_at
    ? new Date(sub.expires_at).toLocaleDateString(locale)
    : t("common.none");

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t("sub.title")}</h1>
        <p className="text-slate-600 mt-1 text-sm">{t("sub.lead")}</p>
      </div>

      <Card title={t("sub.current")}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="text-2xl font-semibold text-slate-900">
              {PLAN_LABEL[currentPlan]}
            </div>
            <div className="text-xs text-slate-500 mt-2">
              {t("sub.status")}:{" "}
              <Badge tone={sub?.status === "active" ? "green" : "amber"}>
                {sub?.status ?? t("sub.no_sub")}
              </Badge>
            </div>
          </div>
          <div className="text-right text-sm">
            <div className="text-slate-500">{t("sub.expires")}</div>
            <div className="font-medium text-slate-900">{expiresLabel}</div>
          </div>
        </div>
      </Card>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-3">
          {t("sub.compare")}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {PLAN_ROWS.map((p) => {
            const isCurrent = p.id === currentPlan;
            const isUpgrade = p.upgradable && PLAN_RANK[p.id] > currentRank;
            return (
              <div
                key={p.id}
                className={clsx(
                  "rounded-2xl border p-5 flex flex-col bg-white",
                  isCurrent
                    ? "border-brand-500 ring-2 ring-brand-500/20"
                    : "border-slate-200",
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="text-base font-semibold text-slate-900">
                    {p.name}
                  </div>
                  {isCurrent && <Badge tone="blue">{t("dash.active")}</Badge>}
                </div>

                <div className="mt-3">
                  <div className="text-3xl font-bold text-slate-900">{p.price}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {t(p.periodKey)}
                  </div>
                </div>

                <ul className="mt-4 space-y-2 text-sm text-slate-700 flex-1">
                  <li className="flex items-start gap-2">
                    <Check size={16} className="text-brand-600 mt-0.5 shrink-0" />
                    <span>
                      <strong>{p.emails}</strong> {t("sub.emails_day")}
                    </span>
                  </li>
                  {p.featureKeys.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check size={16} className="text-brand-600 mt-0.5 shrink-0" />
                      <span>{t(f)}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-5">
                  {isUpgrade ? (
                    <a
                      href={`/api/checkout?plan=${p.id}`}
                      target="_blank"
                      rel="noopener"
                      className="w-full inline-flex items-center justify-center gap-1 px-4 py-2 rounded-lg text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white shadow-sm transition-colors"
                    >
                      {t("sub.upgrade")}
                      <ChevronRight size={16} />
                    </a>
                  ) : isCurrent ? (
                    <Button variant="ghost" disabled className="w-full">
                      {t("sub.current_plan")}
                    </Button>
                  ) : (
                    <Button variant="ghost" disabled className="w-full">
                      {t("common.none")}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="text-xs text-slate-500 mt-4">{t("sub.footer")}</div>
      </div>
    </div>
  );
}
