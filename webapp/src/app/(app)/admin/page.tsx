import { redirect } from "next/navigation";
import { serverFetch, ApiError } from "@/lib/api";
import { Badge, Card, Stat } from "@/components/ui";
import type { AdminStats, AdminUsersPage, Me } from "@/lib/types";

export const metadata = { title: "Admin — JYRY AI" };

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const me = await serverFetch<Me>("/api/me");
  if (!me.is_admin) redirect("/app/dashboard");

  const params = await searchParams;
  const page = Number(params.page ?? 1);
  const q = (params.q ?? "").trim();

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
      redirect("/app/dashboard");
    }
    throw err;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Admin</h1>
        <p className="text-slate-600 mt-1 text-sm">
          Übersicht über alle Nutzer, Tarife und Aktivität.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Nutzer insgesamt" value={stats.users_total} />
        <Stat label="Davon aktiv" value={stats.users_active} />
        <Stat label="E-Mails heute" value={stats.emails_sent_today} />
        <Stat label="E-Mails gesamt" value={stats.emails_sent_total} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Stat label="Free" value={stats.users_by_plan.free ?? 0} />
        <Stat label="Plus" value={stats.users_by_plan.plus ?? 0} />
        <Stat label="Pro" value={stats.users_by_plan.pro ?? 0} />
        <Stat label="Max" value={stats.users_by_plan.max ?? 0} />
      </div>

      <Card title={`Nutzer (${users.total})`}>
        <form className="mb-4">
          <input
            name="q"
            defaultValue={q}
            placeholder="Suche nach E-Mail oder Name…"
            className="w-full md:w-96 px-3 py-2 rounded-lg border border-slate-300 text-sm"
          />
        </form>

        <table className="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>E-Mail</th>
              <th>Name</th>
              <th>Tarif</th>
              <th>Status</th>
              <th>Heute</th>
              <th>Gesamt</th>
              <th>Erstellt</th>
            </tr>
          </thead>
          <tbody>
            {users.items.map((u) => (
              <tr key={u.id}>
                <td className="text-slate-400">{u.id}</td>
                <td>
                  {u.email ?? "—"}
                  {u.is_admin && (
                    <Badge tone="amber">
                      <span className="ml-1">admin</span>
                    </Badge>
                  )}
                </td>
                <td>{u.full_name ?? "—"}</td>
                <td>
                  <Badge tone={u.plan === "free" ? "slate" : "blue"}>
                    {u.plan}
                  </Badge>
                </td>
                <td>
                  <Badge tone={u.is_active ? "green" : "slate"}>
                    {u.is_active ? "aktiv" : "pausiert"}
                  </Badge>
                </td>
                <td>{u.emails_sent_today}</td>
                <td>{u.emails_sent_total}</td>
                <td className="text-slate-500">
                  {new Date(u.created_at).toLocaleDateString("de-DE")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
