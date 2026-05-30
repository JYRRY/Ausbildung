import { serverFetch } from "@/lib/api";
import { Card } from "@/components/ui";
import { getLang } from "@/lib/lang";
import { translator } from "@/lib/i18n";
import type { Me } from "@/lib/types";
import { ProfileForm } from "./ProfileForm";
import { NotificationsForm } from "./NotificationsForm";

export const metadata = { title: "Profil — JYRY AI" };

export default async function ProfilePage() {
  const lang = await getLang();
  const t = translator(lang);
  const me = await serverFetch<Me>("/api/me");
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t("profile.title")}</h1>
        <p className="text-slate-600 mt-1 text-sm">{t("profile.lead")}</p>
      </div>

      <Card title={t("profile.personal")}>
        <ProfileForm me={me} lang={lang} />
      </Card>

      <Card title={t("profile.notifications")}>
        <NotificationsForm mode={me.notification_mode} lang={lang} />
      </Card>
    </div>
  );
}
