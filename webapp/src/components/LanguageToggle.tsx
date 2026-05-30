"use client";

import { useRouter } from "next/navigation";
import clsx from "clsx";
import { LANG_COOKIE, type Lang } from "@/lib/i18n";

export function LanguageToggle({ current }: { current: Lang }) {
  const router = useRouter();

  function set(lang: Lang) {
    if (lang === current) return;
    // 1 year, root path so both /app and /api see it.
    document.cookie = `${LANG_COOKIE}=${lang}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
    router.refresh();
  }

  return (
    <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden text-xs">
      {(["de", "en"] as Lang[]).map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => set(l)}
          className={clsx(
            "px-2.5 py-1 font-medium transition-colors",
            current === l
              ? "bg-brand-600 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50",
          )}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
