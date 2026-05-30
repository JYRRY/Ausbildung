import { serverFetch } from "@/lib/api";
import { Badge, Card, Stat } from "@/components/ui";
import { getT } from "@/lib/lang";
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
  const { lang, t } = await getT();
  const [me, recent] = await Promise.all([
    serverFetch<Me>("/api/me"),
    serverFetch<ApplicationsPage>("/api/applications?page=1&page_size=5"),
  ]);

  const sub = me.subscription;
  const plan = sub ? PLAN_LABEL[sub.plan] : t("common.none");
  const remaining = sub ? sub.daily_quota - sub.emails_sent_today : 0;
  const locale = lang === "de" ? "de-DE" : "en-GB";
  const expiresLabel = sub?.expires_at
    ? new Date(sub.expires_at).toLocaleDateString(locale)
    : t("common.none");

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          {t("dash.welcome")}
          {me.full_name ? `, ${me.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="text-slate-600 mt-1 text-sm">{t("dash.lead")}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          label={t("dash.sent_today")}
          value={sub ? sub.emails_sent_today : 0}
          hint={
            sub
              ? t("dash.remaining", { n: remaining, q: sub.daily_quota })
              : t("dash.no_sub")
          }
        />
        <Stat label={t("dash.plan")} value={plan} hint={sub?.status ?? t("common.none")} />
        <Stat
          label={t("dash.shipping")}
          value={
            me.is_active ? (
              <Badge tone="green">{t("dash.active")}</Badge>
            ) : (
              <Badge tone="amber">{t("dash.paused")}</Badge>
            )
          }
          hint={me.onboarding_complete ? t("dash.setup_done") : t("dash.setup_incomplete")}
        />
        <Stat label={t("dash.expires")} value={expiresLabel} />
      </div>

      <Card title={t("dash.shipping")}>
        <ActiveToggle isActive={me.is_active} lang={lang} />
      </Card>

      <Card title={t("dash.recent")}>
        {recent.items.length === 0 ? (
          <div className="text-sm text-slate-500">{t("dash.no_recent")}</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>{t("col.position")}</th>
                <th>{t("col.status")}</th>
                <th>{t("col.date")}</th>
              </tr>
            </thead>
            <tbody>
              {recent.items.map((r) => (
                <tr key={r.id}>
                  <td>{r.job_title ?? t("common.none")}</td>
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
                      ? new Date(r.sent_at).toLocaleString(locale)
                      : new Date(r.created_at).toLocaleString(locale)}
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
