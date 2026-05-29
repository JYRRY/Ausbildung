import { redirect } from "next/navigation";
import { isAuthenticated } from "@/lib/api";

export default async function Index() {
  // /app -> dashboard if logged in, /signin otherwise.
  if (await isAuthenticated()) redirect("/app/dashboard");
  redirect("/app/signin");
}
