import { Check, ChevronRight } from "lucide-react";
import clsx from "clsx";
import { serverFetch } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui";
import type { Me, Plan } from "@/lib/types";

export const metadata = { title: "Abo — JYRY AI" };

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  plus: "Plus",
  pro: "Pro",
  max: "Max",
};

interface PlanRow {
  id: Plan;
  name: string;
  price: string;
  period: string;
  emails: number;
  features: string[];
  upgradable: boolean;
}

const PLAN_ROWS: PlanRow[] = [
  {
    id: "free",
    name: "Free",
    price: "0 €",
    period: "3 Tage Testphase",
    emails: 10,
    features: ["1 Beruf", "1 Bundesland"],
    upgradable: false,
  },
  {
    id: "plus",
    name: "Plus",
    price: "14,99 €",
    period: "pro Monat",
    emails: 30,
    features: ["3 Berufe", "6 Bundesländer"],
    upgradable: true,
  },
  {
    id: "pro",
    name: "Pro",
    price: "29,99 €",
    period: "alle 3 Monate",
    emails: 100,
    features: ["Alle Berufe", "Alle 16 Bundesländer", "Bewerbungs-Vorlagen"],
    upgradable: true,
  },
  {
    id: "max",
    name: "Max",
    price: "69,99 €",
    period: "alle 6 Monate",
    emails: 200,
    features: [
      "Alle Berufe",
      "Alle 16 Bundesländer",
      "Bewerbungs-Vorlagen",
      "24/7 Priority-Support",
    ],
    upgradable: true,
  },
];

const PLAN_RANK: Record<string, number> = { free: 0, plus: 1, pro: 2, max: 3 };

export default async function SubscriptionPage() {
  const me = await serverFetch<Me>("/api/me");
  const sub = me.subscription;
  const currentPlan = (sub?.plan ?? "free") as Plan;
  const currentRank = PLAN_RANK[currentPlan];
  const expiresLabel = sub?.expires_at
    ? new Date(sub.expires_at).toLocaleDateString("de-DE")
    : "—";

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Abo</h1>
        <p className="text-slate-600 mt-1 text-sm">
          Aktueller Tarif, Verlängerung und Upgrade-Optionen.
        </p>
      </div>

      <Card title="Aktueller Tarif">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="text-2xl font-semibold text-slate-900">
              {PLAN_LABEL[currentPlan]}
            </div>
            <div className="text-xs text-slate-500 mt-2">
              Status:{" "}
              <Badge tone={sub?.status === "active" ? "green" : "amber"}>
                {sub?.status ?? "kein Abo"}
              </Badge>
            </div>
          </div>
          <div className="text-right text-sm">
            <div className="text-slate-500">Läuft bis</div>
            <div className="font-medium text-slate-900">{expiresLabel}</div>
          </div>
        </div>
      </Card>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-3">
          Tarife im Vergleich
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
                  {isCurrent && <Badge tone="blue">aktiv</Badge>}
                </div>

                <div className="mt-3">
                  <div className="text-3xl font-bold text-slate-900">
                    {p.price}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">{p.period}</div>
                </div>

                <ul className="mt-4 space-y-2 text-sm text-slate-700 flex-1">
                  <li className="flex items-start gap-2">
                    <Check size={16} className="text-brand-600 mt-0.5 shrink-0" />
                    <span>
                      <strong>{p.emails}</strong> E-Mails / Tag
                    </span>
                  </li>
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <Check size={16} className="text-brand-600 mt-0.5 shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-5">
                  {isUpgrade ? (
                    // Raw <a> on purpose: /api/* is FastAPI behind nginx, not a
                    // Next.js route, so we must NOT have Next prefix /app to it.
                    <a
                      href={`/api/checkout?plan=${p.id}`}
                      target="_blank"
                      rel="noopener"
                      className="w-full inline-flex items-center justify-center gap-1 px-4 py-2 rounded-lg text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white shadow-sm transition-colors"
                    >
                      Upgrade
                      <ChevronRight size={16} />
                    </a>
                  ) : isCurrent ? (
                    <Button variant="ghost" disabled className="w-full">
                      Aktueller Tarif
                    </Button>
                  ) : (
                    <Button variant="ghost" disabled className="w-full">
                      —
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="text-xs text-slate-500 mt-4">
          Upgrades werden anteilig nach Nutzung berechnet. Die Abwicklung
          erfolgt über Paddle; Verlängerungen sind automatisch und können
          jederzeit deaktiviert werden.
        </div>
      </div>
    </div>
  );
}
