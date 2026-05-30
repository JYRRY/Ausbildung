import { cookies } from "next/headers";
import { DEFAULT_LANG, LANG_COOKIE, type Lang, translator } from "./i18n";

/** Read the active language from the cookie (server components only). */
export async function getLang(): Promise<Lang> {
  const ck = await cookies();
  const v = ck.get(LANG_COOKIE)?.value;
  return v === "en" || v === "de" ? v : DEFAULT_LANG;
}

/** Convenience: language + bound translator in one call. */
export async function getT() {
  const lang = await getLang();
  return { lang, t: translator(lang) };
}
