"""All German user-facing strings — single source of truth.

Kept as plain module-level constants (no .po files, no gettext) because
the bot is German-only by design. Templated strings use ``str.format`` with
named placeholders, e.g. ``messages.STATUS.format(sent=3, remaining=27)``.
"""

from __future__ import annotations

SUBSCRIBE_REQUIRED = (
    "🔒 *Zugang nur für Abonnenten*\n\n"
    "Um JYRY AI nutzen zu können, abonniere bitte zuerst unseren Telegram-Kanal. "
    "Klicke danach auf »Ich habe abonniert«, um fortzufahren."
)
SUBSCRIBE_BUTTON = "📢 Kanal abonnieren"
SUBSCRIBE_CHECK_BUTTON = "✅ Ich habe abonniert"
SUBSCRIBE_STILL_NOT_MEMBER = (
    "❌ Du bist noch nicht im Kanal. Bitte abonniere ihn und versuche es erneut."
)
SUBSCRIBE_SUCCESS = (
    "✅ Danke fürs Abonnieren! Sende /start, um JYRY AI zu nutzen."
)

WELCOME = (
    "👋 Willkommen bei *JYRY AI* — dem Assistenten, der deine Bewerbungen an "
    "Ausbildungsbetriebe in ganz Deutschland für dich verschickt.\n\n"
    "Wähle unten, wie du fortfahren möchtest."
)

WELCOME_BACK = (
    "👋🏽 *Willkommen zurück{name_suffix}!*\n\n"
    "✅ Deine Daten sind gespeichert\n"
    "{progress}\n\n"
    "Klicke auf *▶️ Loslegen* um direkt dort weiterzumachen, wo du aufgehört hast."
)

MAIN_MENU_TITLE = "🏠 Hauptmenü — was möchtest du tun?"

ABOUT = (
    "ℹ️ *Über JYRY AI*\n\n"  # noqa: RUF001
    "JYRY AI sucht täglich neue Ausbildungsangebote der Bundesagentur für "
    "Arbeit und versendet automatisch in deinem Namen Bewerbungs-E-Mails an "
    "die Arbeitgeber. Der Versand erfolgt von deinem eigenen Gmail-Konto über "
    "ein App-Passwort, das verschlüsselt gespeichert wird.\n\n"
    "Vorteile:\n"
    "• Du sparst Stunden manueller Recherche und Bewerbung.\n"
    "• Jeder Arbeitgeber wird höchstens einmal angeschrieben.\n"
    "• Versand wird über den Tag verteilt, um Spam-Filter zu umgehen."
)

PLANS_TITLE = (
    "💳 *Tarife*\n\n"
    "• *Free* — 0 € · 3 Tage Testphase · 5 E-Mails/Tag · 1 Beruf · 1 Bundesland\n"
    "• *Plus* — 14,99 €/Monat · 30 E-Mails/Tag · 3 Berufe · 6 Bundesländer\n"
    "• *Pro* — 29,99 € für 3 Monate · 100 E-Mails/Tag · alle Berufe · alle Länder\n"
    "• *Max* — 99 €/Jahr · 100 E-Mails/Tag · alle Berufe · alle Länder · 24/7-Support\n\n"
    "Wähle einen Tarif, um zur Bezahlung weitergeleitet zu werden."
)

PLAN_CHECKOUT_PLACEHOLDER = (
    "🔧 Die Bezahlung über Lemon Squeezy wird im nächsten Update aktiviert. "
    "Wähle in der Zwischenzeit *Free* (3 Tage Testphase), um die Funktionen zu testen."
)
PLAN_CHECKOUT_READY = (
    "✅ Dein Zahlungslink wurde erstellt. Klicke auf den Button unten, "
    "um deinen Tarif zu aktivieren. Nach der Zahlung kannst du sofort loslegen."
)
PLAN_FREE_ACTIVATED = (
    "✅ Free-Testphase aktiviert (gültig 3 Tage). Du kannst jetzt mit dem Setup beginnen."
)
CHECKOUT_BUTTON = "💳 Jetzt kaufen"

NEED_SUBSCRIPTION_FIRST = (
    "Bevor du loslegen kannst, wähle bitte einen Tarif. Tippe unten auf *Tarife*."
)

CONSENT_WARNING = (
    "⚠️ *Wichtige Hinweise vor dem Start*\n\n"
    "1. Massen-E-Mails an Unternehmen können in Deutschland unter Umständen "
    "gegen das UWG (§7 unzumutbare Belästigung) verstoßen, wenn kein "
    "tatsächliches Interesse an einer Ausbildung besteht. Verschicke nur "
    "Bewerbungen für Stellen, die zu dir passen.\n"
    "2. Du bleibst jederzeit verantwortlicher Absender. Inhalt und Anhänge "
    "müssen wahrheitsgemäß sein.\n"
    "3. Gmail kann dein Konto sperren, wenn du in kurzer Zeit zu viele "
    "E-Mails verschickst. JYRY AI verteilt deshalb den Versand automatisch.\n"
    "4. Wir speichern dein App-Passwort *verschlüsselt* (Fernet) und nutzen "
    "es ausschließlich zum SMTP-Login.\n\n"
    "Bestätige unten, dass du diese Punkte verstanden hast und zustimmst."
)
CONSENT_BUTTON_ACCEPT = "✅ Ich habe verstanden und stimme zu"
CONSENT_BUTTON_DECLINE = "❌ Abbrechen"

ASK_NAME = (
    "Wie lautet dein vollständiger Name? Er erscheint als Absendername in "
    "deinen Bewerbungs-E-Mails."
)

ASK_GMAIL_ADDRESS = (
    "Welche Gmail-Adresse soll für den Versand verwendet werden?\n"
    "(z. B. `vorname.nachname@gmail.com`)"
)
INVALID_EMAIL = (
    "Das sieht nicht wie eine gültige Gmail-Adresse aus. "
    "Bitte gib eine gültige Adresse ein (z. B. `name@gmail.com`)."
)

APP_PASSWORD_INSTRUCTIONS = (
    "🔐 *Google-App-Passwort einrichten*\n\n"
    "⚠️ *Wichtig:* App-Passwörter sind nur verfügbar, wenn die "
    "*Bestätigung in zwei Schritten (2FA) aktiviert* ist. Ohne 2FA "
    "wird die Seite für App-Passwörter in deinem Google-Konto nicht "
    "angezeigt.\n\n"
    "1. *Schritt 1 — 2FA aktivieren* (falls noch nicht aktiv):\n"
    "   Öffne https://myaccount.google.com/signinoptions/two-step-verification "
    "und folge den Anweisungen.\n\n"
    "2. *Schritt 2 — App-Passwort erstellen:*\n"
    "   Öffne https://myaccount.google.com/apppasswords und erstelle "
    "ein neues App-Passwort namens *JYRY AI*.\n\n"
    "3. *Schritt 3 — Senden:*\n"
    "   Google zeigt dir *genau 16 Zeichen* — kopiere sie und sende sie "
    "mir hier in der nächsten Nachricht.\n\n"
    "Deine Nachricht wird nach dem Speichern *sofort gelöscht* und das "
    "Passwort wird nur verschlüsselt abgelegt."
)
APP_PASSWORD_SAVED = "🔒 Gespeichert (verschlüsselt). Weiter geht's…"
APP_PASSWORD_SKIP_LABEL = "✅ Bereits verknüpft"
APP_PASSWORD_SKIPPED_NOTICE = (
    "✅ Bestehende Gmail-Verknüpfung übernommen. Weiter geht's…"
)
APP_PASSWORD_INVALID_LENGTH = (
    "❌ Das App-Passwort muss *genau 16 Zeichen* lang sein "
    "(Leerzeichen werden ignoriert). Bitte kopiere die 16 Zeichen erneut "
    "aus deinem Google-Konto und sende sie noch einmal."
)

ASK_SPECIALTIES = (
    "🎯 Wähle die Berufe, für die du dich bewerben möchtest. "
    "Tippe einen Eintrag, um ihn zu (de-)aktivieren. "
    "Erlaubte Anzahl in deinem Tarif: *{cap}*."
)
ASK_SPECIALTIES_NO_CAP = (
    "🎯 Wähle die Berufe, für die du dich bewerben möchtest."
)
SPECIALTIES_CAP_REACHED = "Du hast bereits die maximale Anzahl ({cap}) ausgewählt."
SPECIALTIES_NEED_AT_LEAST_ONE = "Bitte wähle mindestens einen Beruf."

ASK_STATES = (
    "🗺️ Wähle die Bundesländer, in denen du suchen möchtest. "
    "Erlaubte Anzahl: *{cap}*."
)
ASK_STATES_NO_CAP = "🗺️ Wähle die Bundesländer, in denen du suchen möchtest."
STATES_CAP_REACHED = "Du hast bereits die maximale Anzahl ({cap}) ausgewählt."
STATES_NEED_AT_LEAST_ONE = "Bitte wähle mindestens ein Bundesland."

ASK_EMAIL_BODY = (
    "✉️ Schreibe jetzt den Bewerbungstext, der an jeden Arbeitgeber "
    "verschickt wird.\n\n"
    "Tipp: Verwende `{{company}}`, um den Firmennamen automatisch "
    "einsetzen zu lassen — z. B. *„Sehr geehrte Damen und Herren der "
    "{{company}}, …\".*"
)
ASK_EMAIL_SUBJECT = (
    "✉️ *Betreffzeile*\n\n"
    "Welcher Betreff soll deine Bewerbung haben?\n\n"
    "Tipp: Verwende `{{company}}`, um den Firmennamen automatisch "
    "einsetzen zu lassen — z. B. *„Bewerbung um eine Ausbildungsstelle "
    "bei {{company}}\"*."
)

ASK_ATTACHMENTS = (
    "📎 Sende mir jetzt deine Bewerbungsunterlagen als PDF (Lebenslauf, "
    "Zeugnisse). Du kannst mehrere Dateien hintereinander senden. "
    "Wenn du fertig bist, tippe unten auf *Fertig*."
)
ATTACHMENT_SAVED = "✅ Anhang gespeichert: *{filename}* ({size_kb} KB)."
ATTACHMENT_REMOVED = "🗑️ Anhang entfernt: *{filename}*."
ATTACHMENT_REJECTED_TYPE = (
    "Nur PDF-Dateien werden akzeptiert. Bitte sende eine PDF."
)
ATTACHMENT_REJECTED_SIZE = (
    "Diese Datei ist zu groß (Limit 10 MB). Bitte sende eine kleinere Datei."
)
ATTACHMENTS_NEED_AT_LEAST_ONE = (
    "Bitte sende mindestens einen Anhang (Lebenslauf), bevor du fortfährst."
)

CONFIRM_PROMPT = (
    "🚀 *Fertig!* JYRY AI ist bereit, im Hintergrund Bewerbungen für dich zu "
    "versenden.\n\n"
    "Tippe *Versand starten*, um zu beginnen."
)
CONFIRM_BUTTON = "🚀 Versand starten"

ONBOARDING_DONE = (
    "✅ Du bist startklar! Der erste Versand erfolgt in wenigen Minuten. "
    "Tippe jederzeit auf *Status*, um deinen Fortschritt zu sehen."
)

# Main menu (post-onboarding)
MENU_STATUS = "📊 Status"
MENU_EDIT_NAME = "👤 Absendername ändern"
MENU_EDIT_GMAIL = "📧 Gmail-Konto wechseln"
MENU_EDIT_BODY = "✉️ Bewerbungstext bearbeiten"
MENU_EDIT_ATTACHMENTS = "📎 Anhänge bearbeiten"
MENU_EDIT_SPECIALTIES = "🎯 Berufe ändern"
MENU_EDIT_STATES = "🗺️ Bundesländer ändern"
MENU_PAUSE = "⏸️ Versand pausieren"
MENU_RESUME = "▶️ Versand fortsetzen"
MENU_PLAN = "💳 Tarif ansehen"
MENU_SEND_TEST = "🧪 Test-E-Mail senden"

TEST_EMAIL_STARTING = (
    "🚀 *5 Test-E-Mails werden verschickt…*\n\n"
    "Bitte ein paar Sekunden warten — der Bot feuert sie im Free-Trial-"
    "Tempo (≈ 2 Sekunden Abstand) hintereinander ab."
)
TEST_EMAIL_SENT = (
    "✅ *{count} Test-E-Mails verschickt!*\n\n"
    "Empfänger: `{to}`\n\n"
    "Schau in deinem Posteingang nach (auch *Spam* / *Alle Nachrichten*) — "
    "Format, Anhänge und Platzhalter prüfen. Die Betreffzeilen sind "
    "nummeriert *[TEST 1/5]* … *[TEST 5/5]*."
)
TEST_EMAIL_PARTIAL = (
    "⚠️ *Nur {sent} von 5 Test-E-Mails verschickt.*\n\n"
    "Empfänger: `{to}`\n"
    "Letzter Fehler: `{detail}`"
)
TEST_EMAIL_FAILED = (
    "❌ *Test-E-Mail fehlgeschlagen.*\n\n"
    "Grund: `{detail}`\n\n"
    "Prüfe Gmail-Adresse, App-Passwort und ob 2FA aktiv ist."
)
TEST_EMAIL_NOT_READY = (
    "⚠️ Bitte schließe zuerst das Onboarding ab (Gmail, App-Passwort, "
    "Betreff & Text) bevor du eine Test-E-Mail sendest."
)
MENU_ABOUT = "ℹ️ Über JYRY AI"  # noqa: RUF001
MENU_PLANS = "💳 Tarife"
MENU_START = "▶️ Loslegen"

STATUS_TEMPLATE = (
    "📊 *Dein Status*\n\n"
    "Tarif: *{plan}*\n"
    "Heute versendet: *{sent_today}* / {daily_quota}\n"
    "Verbleibend heute: *{remaining}*\n"
    "Insgesamt versendet: *{total_sent}*\n"
    "Versand: *{state}*"
)
STATUS_STATE_ACTIVE = "läuft ✅"
STATUS_STATE_PAUSED = "pausiert ⏸️"

PAUSED_NOTICE = (
    "⏸️ Versand pausiert. Tippe auf *Versand fortsetzen*, wenn du wieder "
    "starten möchtest."
)
RESUMED_NOTICE = "▶️ Versand wieder aktiv. Du erhältst gleich neue Bewerbungen."

SUBSCRIPTION_ACTIVATED_NOTICE = (
    "🎉 *Abonnement aktiv!*\n\n"
    "Dein *{plan}*-Tarif ({daily_quota} Bewerbungen/Tag) ist jetzt "
    "freigeschaltet.\n\n"
    "📊 Tippe auf *Status* im Hauptmenü, um deine Tarif-Details, dein "
    "Tageskontingent und den Versandstatus jederzeit einzusehen.\n\n"
    "Viel Erfolg mit deinen Bewerbungen! 🚀"
)

RENEWAL_REMINDER = (
    "🔔 *Erinnerung*\n\n"
    "Dein *{plan}*-Tarif wird in 3 Tagen automatisch verlängert.\n\n"
    "💳 *{price} €* werden von deiner hinterlegten Karte abgebucht.\n"
    "✅ Der Bot läuft ohne Unterbrechung weiter.\n\n"
    "Möchtest du nicht verlängern? Du kannst dein Abo jederzeit über "
    "Lemon Squeezy kündigen."
)

UNKNOWN_COMMAND = (
    "Ich habe das nicht verstanden. Tippe /start, um zum Menü zurückzukehren."
)

BACK_LABEL = "⬅️ Zurück"
DONE_LABEL = "✅ Fertig"
CANCEL_LABEL = "❌ Abbrechen"
NEXT_LABEL = "Weiter ➡️"
FORWARD_LABEL = "➡️ Weiter"
MENU_LABEL = "🏠 Menü"
FORWARD_FIELD_EMPTY = (
    "⚠️ Dieses Feld ist noch leer — bitte trage etwas ein, "
    "bevor du weitergehst."
)


# Used by tests to assert no key is missing/empty.
ALL_KEYS: tuple[str, ...] = (
    "WELCOME",
    "WELCOME_BACK",
    "MAIN_MENU_TITLE",
    "ABOUT",
    "PLANS_TITLE",
    "PLAN_CHECKOUT_PLACEHOLDER",
    "PLAN_CHECKOUT_READY",
    "PLAN_FREE_ACTIVATED",
    "CHECKOUT_BUTTON",
    "NEED_SUBSCRIPTION_FIRST",
    "CONSENT_WARNING",
    "CONSENT_BUTTON_ACCEPT",
    "CONSENT_BUTTON_DECLINE",
    "ASK_NAME",
    "ASK_GMAIL_ADDRESS",
    "INVALID_EMAIL",
    "APP_PASSWORD_INSTRUCTIONS",
    "APP_PASSWORD_SAVED",
    "APP_PASSWORD_INVALID_LENGTH",
    "APP_PASSWORD_SKIP_LABEL",
    "APP_PASSWORD_SKIPPED_NOTICE",
    "ASK_SPECIALTIES",
    "ASK_SPECIALTIES_NO_CAP",
    "SPECIALTIES_CAP_REACHED",
    "SPECIALTIES_NEED_AT_LEAST_ONE",
    "ASK_STATES",
    "ASK_STATES_NO_CAP",
    "STATES_CAP_REACHED",
    "STATES_NEED_AT_LEAST_ONE",
    "ASK_EMAIL_BODY",
    "ASK_EMAIL_SUBJECT",
    "ASK_ATTACHMENTS",
    "ATTACHMENT_SAVED",
    "ATTACHMENT_REMOVED",
    "ATTACHMENT_REJECTED_TYPE",
    "ATTACHMENT_REJECTED_SIZE",
    "ATTACHMENTS_NEED_AT_LEAST_ONE",
    "CONFIRM_PROMPT",
    "CONFIRM_BUTTON",
    "ONBOARDING_DONE",
    "MENU_STATUS",
    "MENU_EDIT_NAME",
    "MENU_EDIT_GMAIL",
    "MENU_EDIT_BODY",
    "MENU_EDIT_ATTACHMENTS",
    "MENU_EDIT_SPECIALTIES",
    "MENU_EDIT_STATES",
    "MENU_PAUSE",
    "MENU_RESUME",
    "MENU_PLAN",
    "MENU_SEND_TEST",
    "TEST_EMAIL_STARTING",
    "TEST_EMAIL_SENT",
    "TEST_EMAIL_PARTIAL",
    "TEST_EMAIL_FAILED",
    "TEST_EMAIL_NOT_READY",
    "MENU_ABOUT",
    "MENU_PLANS",
    "MENU_START",
    "STATUS_TEMPLATE",
    "STATUS_STATE_ACTIVE",
    "STATUS_STATE_PAUSED",
    "PAUSED_NOTICE",
    "RESUMED_NOTICE",
    "SUBSCRIPTION_ACTIVATED_NOTICE",
    "RENEWAL_REMINDER",
    "UNKNOWN_COMMAND",
    "BACK_LABEL",
    "DONE_LABEL",
    "CANCEL_LABEL",
    "NEXT_LABEL",
    "FORWARD_LABEL",
    "MENU_LABEL",
    "FORWARD_FIELD_EMPTY",
)
