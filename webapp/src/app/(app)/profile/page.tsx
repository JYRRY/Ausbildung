import { serverFetch } from "@/lib/api";
import { Card } from "@/components/ui";
import type { Me } from "@/lib/types";
import { ProfileForm } from "./ProfileForm";
import { NotificationsForm } from "./NotificationsForm";
import { ActiveToggle } from "./ActiveToggle";

export const metadata = { title: "Profil — JYRY AI" };

export default async function ProfilePage() {
  const me = await serverFetch<Me>("/api/me");
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Profil</h1>
        <p className="text-slate-600 mt-1 text-sm">
          Verwalte deinen Absendernamen, dein Gmail-Konto und deine
          Versand-Einstellungen.
        </p>
      </div>

      <Card title="Persönliche Daten">
        <ProfileForm me={me} />
      </Card>

      <Card title="Benachrichtigungen">
        <NotificationsForm mode={me.notification_mode} />
      </Card>

      <Card title="Versand">
        <ActiveToggle isActive={me.is_active} />
      </Card>
    </div>
  );
}
