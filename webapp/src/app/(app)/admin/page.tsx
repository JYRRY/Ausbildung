import { redirect } from "next/navigation";
import { Mail, Send, UserCheck, Users } from "lucide-react";
import { serverFetch, ApiError } from "@/lib/api";
import { Badge, Card, Stat } from "@/components/ui";
import { getT } from "@/lib/lang";
import type { AdminStats, AdminUsersPage, Me } from "@/lib/types";

export const metadata = { title: "Admin — JYRY AI" };

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const { lang, t } = await getT();
  const me = await serverFetch<Me>("/api/me");
  if (!me.is_admin) redirect("/dashboard");

  const params = await searchParams;
  const page = Number(params.page ?? 1);
  const q = (params.q ?? "").trim();
  const locale = lang === "de" ? "de-DE" : "en-GB";

  let stats: AdminStats | null = null;
  let users: AdminUsersPage | null = null;
  try {
    [stats, users] = await Promise.all([
      serverFetch<AdminStats>("/api/admin/stats"),
      serverFetch<AdminUsersPage>(
        `/api/admin/users?page=${page}&page_size=25${q ? `&q=${encodeURIComponent(q)}` : ""}`,
      ),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      redirect("/dashboard");
    }
    throw err;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t("admin.title")}</h1>
        <p className="text-slate-600 mt-1 text-sm">{t("admin.lead")}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          label={t("admin.users_total")}
          value={stats.users_total}
          icon={<Users size={20} />}
        />
        <Stat
          label={t("admin.users_active")}
          value={stats.users_active}
          icon={<UserCheck size={20} />}
        />
        <Stat
          label={t("admin.emails_today")}
          value={stats.emails_sent_today}
          icon={<Mail size={20} />}
        />
        <Stat
          label={t("admin.emails_total")}
          value={stats.emails_sent_total}
          icon={<Send size={20} />}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Stat label="Free" value={stats.users_by_plan.free ?? 0} />
        <Stat label="Plus" value={stats.users_by_plan.plus ?? 0} />
        <Stat label="Pro" value={stats.users_by_plan.pro ?? 0} />
        <Stat label="Max" value={stats.users_by_plan.max ?? 0} />
      </div>

      <Card title={`${t("admin.users")} (${users.total})`}>
        <form className="mb-4">
          <input
            name="q"
            defaultValue={q}
            placeholder={t("admin.search")}
            className="w-full md:w-96 px-3 py-2 rounded-lg border border-slate-300 text-sm"
          />
        </form>

        <table className="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>E-Mail</th>
              <th>{t("admin.col_name")}</th>
              <th>{t("admin.col_plan")}</th>
              <th>{t("col.status")}</th>
              <th>{t("admin.col_today")}</th>
              <th>{t("admin.col_total")}</th>
              <th>{t("admin.col_created")}</th>
            </tr>
          </thead>
          <tbody>
            {users.items.map((u) => (
              <tr key={u.id}>
                <td className="text-slate-400">{u.id}</td>
                <td>
                  {u.email ?? t("common.none")}
                  {u.is_admin && (
                    <Badge tone="amber">
                      <span className="ml-1">admin</span>
                    </Badge>
                  )}
                </td>
                <td>{u.full_name ?? t("common.none")}</td>
                <td>
                  <Badge tone={u.plan === "free" ? "slate" : "blue"}>{u.plan}</Badge>
                </td>
                <td>
                  <Badge tone={u.is_active ? "green" : "slate"}>
                    {u.is_active ? t("dash.active") : t("dash.paused")}
                  </Badge>
                </td>
                <td>{u.emails_sent_today}</td>
                <td>{u.emails_sent_total}</td>
                <td className="text-slate-500">
                  {new Date(u.created_at).toLocaleDateString(locale)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
