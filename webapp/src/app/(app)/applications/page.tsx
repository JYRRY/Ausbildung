import { serverFetch } from "@/lib/api";
import { Badge, Card } from "@/components/ui";
import type { ApplicationsPage } from "@/lib/types";

export const metadata = { title: "Bewerbungen — JYRY AI" };

export default async function ApplicationsListPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const params = await searchParams;
  const page = Number(params.page ?? 1);
  const data = await serverFetch<ApplicationsPage>(
    `/api/applications?page=${page}&page_size=25`,
  );

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Bewerbungen</h1>
        <p className="text-slate-600 mt-1 text-sm">
          Verlauf aller versendeten Bewerbungen.{" "}
          <span className="text-slate-400">
            (Aus Datenschutzgründen wird der Firmenname nicht angezeigt.)
          </span>
        </p>
      </div>

      <Card>
        {data.items.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">
            Noch keine Bewerbungen.
          </div>
        ) : (
          <>
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Stelle</th>
                  <th>Status</th>
                  <th>Versendet</th>
                  <th>Eingereiht</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="text-slate-400">{r.id}</td>
                    <td>{r.job_title ?? "—"}</td>
                    <td>
                      <Badge
                        tone={
                          r.status === "sent"
                            ? "green"
                            : r.status === "failed"
                              ? "red"
                              : r.status === "queued"
                                ? "blue"
                                : "slate"
                        }
                      >
                        {r.status}
                      </Badge>
                    </td>
                    <td className="text-slate-500">
                      {r.sent_at
                        ? new Date(r.sent_at).toLocaleString("de-DE")
                        : "—"}
                    </td>
                    <td className="text-slate-500">
                      {new Date(r.created_at).toLocaleString("de-DE")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pager
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
            />
          </>
        )}
      </Card>
    </div>
  );
}

function Pager({
  page,
  pageSize,
  total,
}: {
  page: number;
  pageSize: number;
  total: number;
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
      <div>
        Seite {page} von {lastPage} — {total} insgesamt
      </div>
      <div className="space-x-2">
        {page > 1 && (
          <a
            href={`?page=${page - 1}`}
            className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            ← Zurück
          </a>
        )}
        {page < lastPage && (
          <a
            href={`?page=${page + 1}`}
            className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            Weiter →
          </a>
        )}
      </div>
    </div>
  );
}
