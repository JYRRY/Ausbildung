import Link from "next/link";

export const metadata = { title: "Anmelden — JYRY AI" };

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <h1 className="text-2xl font-semibold text-slate-900 mb-2">
          Bei JYRY AI anmelden
        </h1>
        <p className="text-sm text-slate-600 mb-8">
          Melde dich mit deinem Google-Konto an, um dein Dashboard, deine
          Bewerbungen und dein Abo zu verwalten.
        </p>

        <a
          href="/api/auth/google/login"
          className="w-full inline-flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg border border-slate-300 hover:bg-slate-50 transition-colors text-sm font-medium text-slate-900"
        >
          <GoogleMark />
          Mit Google fortfahren
        </a>

        <div className="text-xs text-slate-500 mt-8 leading-relaxed">
          Mit der Anmeldung stimmst du unseren{" "}
          <Link href="/terms" className="underline">
            Nutzungsbedingungen
          </Link>{" "}
          und der{" "}
          <Link href="/privacy" className="underline">
            Datenschutzerklärung
          </Link>{" "}
          zu.
        </div>
      </div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.92c1.71-1.58 2.68-3.9 2.68-6.63z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.92-2.26c-.8.54-1.83.87-3.04.87-2.34 0-4.32-1.58-5.03-3.7H.96v2.32A9 9 0 009 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.71A5.4 5.4 0 013.68 9c0-.59.1-1.17.29-1.71V4.96H.96A9 9 0 000 9c0 1.45.35 2.83.96 4.04l3-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 009 0 9 9 0 00.96 4.96l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}
