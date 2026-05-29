import { redirect } from "next/navigation";
import { ApiError, serverFetch } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import type { Me } from "@/lib/types";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let me: Me;
  try {
    me = await serverFetch<Me>("/api/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/signin");
    }
    throw err;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar me={me} />
      <main className="flex-1 p-6 md:p-8 lg:p-10">{children}</main>
    </div>
  );
}
