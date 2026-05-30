import { serverFetch } from "@/lib/api";
import { Badge, Card } from "@/components/ui";
import { getT } from "@/lib/lang";
import type { ApplicationsPage } from "@/lib/types";
import type { T } from "@/lib/i18n";

export const metadata = { title: "Bewerbungen — JYRY AI" };

export default async function ApplicationsListPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { lang, t } = await getT();
  const params = await searchParams;
  const page = Number(params.page ?? 1);
  const locale = lang === "de" ? "de-DE" : "en-GB";
  const data = await serverFetch<ApplicationsPage>(
    `/api/applications?page=${page}&page_size=25`,
  );

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t("apps.title")}</h1>
        <p className="text-slate-600 mt-1 text-sm">
          {t("apps.lead")}{" "}
          <span className="text-slate-400">{t("apps.privacy_note")}</span>
        </p>
      </div>

      <Card>
        {data.items.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">
            {t("apps.empty")}
          </div>
        ) : (
          <>
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t("col.position")}</th>
                  <th>{t("col.status")}</th>
                  <th>{t("apps.col_sent")}</th>
                  <th>{t("apps.col_queued")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="text-slate-400">{r.id}</td>
                    <td>{r.job_title ?? t("common.none")}</td>
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
                        ? new Date(r.sent_at).toLocaleString(locale)
                        : t("common.none")}
                    </td>
                    <td className="text-slate-500">
                      {new Date(r.created_at).toLocaleString(locale)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pager
              page={data.page}
              pageSize={data.page_size}
              total={data.total}
              t={t}
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
  t,
}: {
  page: number;
  pageSize: number;
  total: number;
  t: T;
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
      <div>{t("apps.page_of", { p: page, last: lastPage, total })}</div>
      <div className="space-x-2">
        {page > 1 && (
          <a
            href={`?page=${page - 1}`}
            className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            {t("apps.prev")}
          </a>
        )}
        {page < lastPage && (
          <a
            href={`?page=${page + 1}`}
            className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            {t("apps.next")}
          </a>
        )}
      </div>
    </div>
  );
}
