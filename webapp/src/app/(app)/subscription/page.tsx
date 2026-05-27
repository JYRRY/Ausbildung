import { serverFetch } from "@/lib/api";
import { Badge, Button, Card } from "@/components/ui";
import type { Me } from "@/lib/types";

export const metadata = { title: "Abo — JYRY AI" };

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  plus: "Plus",
  pro: "Pro",
  max: "Max",
};

const PLAN_PRICE: Record<string, string> = {
  free: "0 € · 3 Tage Testphase",
  plus: "14,99 €/Monat",
  pro: "29,99 € / 3 Monate",
  max: "99 € / 6 Monate",
};

export default async function SubscriptionPage() {
  const me = await serverFetch<Me>("/api/me");
  const sub = me.subscription;
  const plan = sub?.plan ?? "free";
  const planLabel = PLAN_LABEL[plan];
  const expiresLabel = sub?.expires_at
    ? new Date(sub.expires_at).toLocaleDateString("de-DE")
    : "—";

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Abo</h1>
        <p className="text-slate-600 mt-1 text-sm">
          Aktueller Tarif, Verlängerung und Upgrade-Optionen.
        </p>
      </div>

      <Card title="Aktueller Tarif">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-2xl font-semibold text-slate-900">{planLabel}</div>
            <div className="text-sm text-slate-500 mt-1">{PLAN_PRICE[plan]}</div>
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

      <Card title="Tarife im Vergleich">
        <table className="tbl">
          <thead>
            <tr>
              <th>Tarif</th>
              <th>E-Mails/Tag</th>
              <th>Preis</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Free</td>
              <td>10</td>
              <td>0 €</td>
              <td></td>
            </tr>
            <tr>
              <td>Plus</td>
              <td>30</td>
              <td>14,99 €/Mon.</td>
              <td>
                {plan !== "plus" && plan === "free" && (
                  <UpgradeLink target="plus" />
                )}
              </td>
            </tr>
            <tr>
              <td>Pro</td>
              <td>100</td>
              <td>29,99 € / 3 Mon.</td>
              <td>
                {plan !== "pro" && plan !== "max" && (
                  <UpgradeLink target="pro" />
                )}
              </td>
            </tr>
            <tr>
              <td>Max</td>
              <td>200</td>
              <td>99 € / 6 Mon.</td>
              <td>{plan !== "max" && <UpgradeLink target="max" />}</td>
            </tr>
          </tbody>
        </table>

        <div className="text-xs text-slate-500 mt-3">
          Upgrades werden anteilig nach Nutzung berechnet. Der Versand wird über
          Paddle abgewickelt; Verlängerungen erfolgen automatisch und können
          jederzeit deaktiviert werden.
        </div>
      </Card>

      {sub?.auto_renew && (
        <Card title="Auto-Verlängerung">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-600">
              Dein Abo verlängert sich automatisch am {expiresLabel}.
            </div>
            <Button variant="ghost">Auto-Verlängerung deaktivieren</Button>
          </div>
          <div className="text-xs text-slate-400 mt-2">
            (Folgt — wird über die Paddle-Verwaltung im Bot abgeschlossen.)
          </div>
        </Card>
      )}
    </div>
  );
}

function UpgradeLink({ target }: { target: "plus" | "pro" | "max" }) {
  return (
    <a
      href={`/api/checkout?plan=${target}`}
      className="inline-block px-3 py-1 rounded-lg border border-brand-500 text-brand-600 text-xs hover:bg-brand-50"
    >
      Upgrade
    </a>
  );
}
