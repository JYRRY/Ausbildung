import { serverFetch } from "@/lib/api";
import { Badge, Card, Stat } from "@/components/ui";
import type { ApplicationsPage, Me } from "@/lib/types";
import { ActiveToggle } from "../profile/ActiveToggle";

export const metadata = { title: "Dashboard — JYRY AI" };

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  plus: "Plus",
  pro: "Pro",
  max: "Max",
};

export default async function DashboardPage() {
  const [me, recent] = await Promise.all([
    serverFetch<Me>("/api/me"),
    serverFetch<ApplicationsPage>("/api/applications?page=1&page_size=5"),
  ]);

  const sub = me.subscription;
  const plan = sub ? PLAN_LABEL[sub.plan] : "—";
  const remaining = sub ? sub.daily_quota - sub.emails_sent_today : 0;
  const expiresLabel = sub?.expires_at
    ? new Date(sub.expires_at).toLocaleDateString("de-DE")
    : "—";

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Willkommen{me.full_name ? `, ${me.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="text-slate-600 mt-1 text-sm">
          Hier ist der Überblick über deinen Versand und dein Abo.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          label="Heute versendet"
          value={sub ? sub.emails_sent_today : 0}
          hint={sub ? `${remaining} verbleibend von ${sub.daily_quota}` : "Kein Abo"}
        />
        <Stat label="Tarif" value={plan} hint={sub?.status ?? "—"} />
        <Stat
          label="Versand"
          value={
            me.is_active ? (
              <Badge tone="green">aktiv</Badge>
            ) : (
              <Badge tone="amber">pausiert</Badge>
            )
          }
          hint={me.onboarding_complete ? "Setup abgeschlossen" : "Setup unvollständig"}
        />
        <Stat label="Läuft bis" value={expiresLabel} />
      </div>

      <Card title="Versand">
        <ActiveToggle isActive={me.is_active} />
      </Card>

      <Card title="Letzte Aktivität">
        {recent.items.length === 0 ? (
          <div className="text-sm text-slate-500">
            Noch keine Bewerbungen versendet.
          </div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Stelle</th>
                <th>Status</th>
                <th>Datum</th>
              </tr>
            </thead>
            <tbody>
              {recent.items.map((r) => (
                <tr key={r.id}>
                  <td>{r.job_title ?? "—"}</td>
                  <td>
                    <Badge
                      tone={
                        r.status === "sent"
                          ? "green"
                          : r.status === "failed"
                            ? "red"
                            : "slate"
                      }
                    >
                      {r.status}
                    </Badge>
                  </td>
                  <td className="text-slate-500">
                    {r.sent_at
                      ? new Date(r.sent_at).toLocaleString("de-DE")
                      : new Date(r.created_at).toLocaleString("de-DE")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
