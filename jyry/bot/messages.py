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
    "• *Free* — 0 € · 3 Tage Testphase · 10 E-Mails/Tag · 1 Beruf · 1 Bundesland\n"
    "• *Plus* — 14,99 €/Monat · 30 E-Mails/Tag · 3 Berufe · 6 Bundesländer\n"
    "• *Pro* — 29,99 € für 3 Monate · 100 E-Mails/Tag · alle Berufe · alle Länder\n"
    "• *Max* — 69,99 € für 6 Monate · 200 E-Mails/Tag · alle Berufe · alle Länder · 24/7-Support\n\n"
    "Wähle einen Tarif, um zur Bezahlung weitergeleitet zu werden."
)

PLANS_TITLE_ACTIVE = (
    "💳 *Dein Tarif: {plan}*\n\n"
    "Du kannst jederzeit auf einen höheren Tarif upgraden — die Differenz wird "
    "von Paddle anteilig berechnet und sofort von deiner hinterlegten "
    "Karte abgebucht. Ein Downgrade ist nicht möglich.\n\n"
    "Möchtest du dein Abo beenden, nutze *Abo kündigen*. Die automatische "
    "Verlängerung wird deaktiviert, dein Tarif bleibt aber bis zum Ende der "
    "bereits bezahlten Laufzeit aktiv."
)
PLAN_ALREADY_MAX = (
    "🏆 Du nutzt bereits unseren höchsten Tarif (*Max*). "
    "Es gibt keinen höheren Tarif zum Upgraden."
)
PLAN_UPGRADE_CONFIRM = (
    "🔄 *Upgrade auf {target_plan}*\n\n"
    "Aktueller Tarif: *{current_plan}*\n"
    "Neuer Tarif: *{target_plan}* ({target_price} €)\n\n"
    "Bei Bestätigung:\n"
    "• Paddle berechnet den anteiligen Differenzbetrag automatisch\n"
    "• Die Differenz wird sofort von deiner hinterlegten Karte abgebucht\n"
    "• Dein Tarif wird sofort auf *{target_plan}* angehoben\n"
    "• Die nächste reguläre Abbuchung erfolgt am Ende der neuen Laufzeit\n\n"
    "Möchtest du fortfahren?"
)
PLAN_UPGRADE_BUTTON = "✅ Upgrade durchführen"
PLAN_UPGRADE_SUCCESS = (
    "🎉 *Upgrade auf {target_plan} erfolgreich!*\n\n"
    "Dein neuer Tarif ist sofort aktiv. Die Tageskontingente und Limits "
    "wurden entsprechend angepasst."
)
PLAN_UPGRADE_FAILED = (
    "❌ *Upgrade fehlgeschlagen.*\n\n"
    "Bitte versuche es später erneut oder kontaktiere den Support."
)
PLAN_CANCEL_LABEL = "❌ Abo kündigen"
PLAN_RETENTION_OFFER = (
    "🤔 *Warte kurz — bevor du kündigst!*\n\n"
    "Du nutzt aktuell *{current_plan}*. Wusstest du, dass du für nur "
    "*{delta} € mehr* auf *{target_plan}* upgraden kannst?\n\n"
    "Mit *{target_plan}* bekommst du:\n"
    "{benefits}\n\n"
    "Möchtest du stattdessen upgraden — oder trotzdem kündigen?"
)
PLAN_RETENTION_UPGRADE_BUTTON = "⬆️ Lieber auf {target_plan} upgraden"
PLAN_RETENTION_PROCEED_BUTTON = "❌ Trotzdem kündigen"
PLAN_CANCEL_CONFIRM = (
    "❌ *Abo kündigen*\n\n"
    "Wenn du fortfährst:\n"
    "• Die *automatische Verlängerung* wird deaktiviert\n"
    "• Dein *{plan}*-Tarif bleibt aktiv bis zum Ende der bereits bezahlten "
    "Laufzeit\n"
    "• Danach wird dein Konto automatisch auf *Free* zurückgesetzt\n"
    "• Es erfolgt *keine Rückerstattung* für die laufende Periode\n\n"
    "Möchtest du wirklich kündigen?"
)
PLAN_CANCEL_CONFIRM_BUTTON = "✅ Ja, Abo kündigen"
PLAN_CANCEL_SUCCESS = (
    "✅ *Abo gekündigt.*\n\n"
    "Die automatische Verlängerung ist deaktiviert. Dein *{plan}*-Tarif "
    "bleibt aktiv bis zum Ende der bereits bezahlten Laufzeit."
)
PLAN_CANCEL_FAILED = (
    "❌ *Kündigung fehlgeschlagen.*\n\n"
    "Bitte versuche es später erneut oder kontaktiere den Support."
)
PLAN_UPGRADE_PREFIX = "⬆️ Upgrade auf "

PLAN_CHECKOUT_PLACEHOLDER = (
    "🔧 Die Bezahlung über Paddle wird im nächsten Update aktiviert. "
    "Wähle in der Zwischenzeit *Free* (3 Tage Testphase), um die Funktionen zu testen."
)
PLAN_CHECKOUT_READY = (
    "✅ Dein Zahlungslink wurde erstellt. Klicke auf den Button unten, "
    "um deinen Tarif zu aktivieren. Nach der Zahlung kannst du sofort loslegen."
)
PLAN_FREE_ACTIVATED = (
    "🎉 *Deine kostenlose Testphase ist gestartet!*\n\n"
    "📅 Gültig *3 Tage* — bis zum *{expires_date}*\n"
    "📧 *10 Bewerbungs-E-Mails* pro Tag\n"
    "🎯 1 Beruf · 1 Bundesland\n\n"
    "⚠️ Nach Ablauf der Testphase wird der automatische Versand gestoppt. "
    "Um weiterzumachen, kannst du jederzeit auf einen bezahlten Tarif upgraden "
    "(*Plus*, *Pro* oder *Max*).\n\n"
    "Jetzt geht's mit dem Setup los 👇"
)
NOTIFICATIONS_PROMPT = (
    "🔔 *Benachrichtigungen*\n\n"
    "Wie möchtest du über versendete Bewerbungen informiert werden?\n\n"
    "🔔 *Pro Bewerbung* — eine kurze Nachricht nach jeder gesendeten E-Mail\n"
    "📊 *Tagesbericht* — eine Zusammenfassung am Ende des Tages\n"
    "🔕 *Aus* — keine Benachrichtigungen\n\n"
    "Du kannst diese Einstellung jederzeit im Hauptmenü ändern."
)
NOTIFICATIONS_BUTTON_PER_SEND = "🔔 Pro Bewerbung"
NOTIFICATIONS_BUTTON_DAILY = "📊 Tagesbericht"
NOTIFICATIONS_BUTTON_OFF = "🔕 Aus"

NOTIFICATION_CONFIRM_PER_SEND = (
    "✅ Du erhältst nach jeder versendeten Bewerbung eine kurze Nachricht."
)
NOTIFICATION_CONFIRM_DAILY = (
    "✅ Tagesbericht aktiviert — du bekommst am Ende des Tages eine "
    "Zusammenfassung."
)
NOTIFICATION_CONFIRM_OFF = (
    "✅ Benachrichtigungen deaktiviert. Du kannst sie jederzeit im "
    "Hauptmenü wieder einschalten."
)

# First send of the day — give context (specialties + counter).
NOTIFICATION_EMAIL_SENT_FIRST = (
    "📧 *Erste Bewerbung heute versendet*\n\n"
    "🎯 {specialties}\n"
    "📊 *{sent_today} / {daily_quota}* heute"
)
# Subsequent sends — only the counter to keep the chat tidy.
NOTIFICATION_EMAIL_SENT = "📊 *{sent_today} / {daily_quota}* heute"

NOTIFICATION_DAILY_SUMMARY = (
    "📊 *Tagesbericht*\n\n"
    "✅ *{sent_today}* Bewerbungen heute versendet\n"
    "🎯 Berufe: {specialties}"
)

MENU_NOTIFICATIONS_PER_SEND = "🔔 Benachrichtigungen: Pro Bewerbung"
MENU_NOTIFICATIONS_DAILY = "📊 Benachrichtigungen: Tagesbericht"
MENU_NOTIFICATIONS_OFF = "🔕 Benachrichtigungen: Aus"

FREE_TRIAL_EXPIRED_NOTICE = (
    "⏰ *Deine Free-Testphase ist abgelaufen*\n\n"
    "Die 3-tägige kostenlose Testphase wurde beendet und der automatische "
    "Versand wurde gestoppt.\n\n"
    "Um weiter Bewerbungen zu verschicken, wähle einen bezahlten Tarif:\n"
    "• *Plus* — 14,99 €/Monat · 30 E-Mails/Tag\n"
    "• *Pro* — 29,99 € / 3 Monate · 100 E-Mails/Tag\n"
    "• *Max* — 69,99 € / 6 Monate · 200 E-Mails/Tag · 24/7-Support\n\n"
    "Tippe auf */plans*, um zu upgraden."
)
FREE_TRIAL_ALREADY_USED = (
    "ℹ️ *Free-Testphase bereits genutzt*\n\n"
    "Du hast die kostenlose 3-Tage-Testphase mit diesem Konto bereits verwendet. "
    "Pro Telegram-Konto ist nur eine Testphase möglich.\n\n"
    "Wähle einen bezahlten Tarif (*Plus*, *Pro* oder *Max*), um weiterzumachen."
)
CHECKOUT_BUTTON = "💳 Jetzt kaufen"

NEED_SUBSCRIPTION_FIRST = (
    "Bevor du loslegen kannst, wähle bitte einen Tarif. Tippe unten auf *Tarife*."
)

CONSENT_WARNING = (
    "⚠️ *Wichtige Hinweise vor dem Start*\n\n"
    "1. Du bleibst jederzeit verantwortlicher Absender. Inhalt und Anhänge "
    "müssen wahrheitsgemäß sein und dürfen nicht irreführend sein.\n"
    "2. Jeder Arbeitgeber wird höchstens *einmal pro Nutzer* angeschrieben.\n"
    "3. Gmail kann dein Konto sperren, wenn du in kurzer Zeit zu viele "
    "E-Mails verschickst. JYRY AI verteilt den Versand deshalb automatisch "
    "über den Tag.\n"
    "4. Dein Gmail-App-Passwort wird *verschlüsselt* (Fernet) gespeichert "
    "und ausschließlich für den SMTP-Login verwendet — niemals an Dritte "
    "weitergegeben.\n"
    "5. Free-Testphase: 3 Tage gültig, 10 E-Mails/Tag. Pro Telegram-Konto "
    "ist nur eine Testphase möglich. Danach ist ein Upgrade auf einen "
    "bezahlten Tarif erforderlich, um den Versand fortzusetzen.\n\n"
    "Bestätige unten, dass du diese Punkte verstanden hast und zustimmst."
)
CONSENT_BUTTON_ACCEPT = "✅ Ich habe verstanden und stimme zu"
CONSENT_BUTTON_DECLINE = "❌ Abbrechen"
CONSENT_REQUIRED = (
    "⚠️ Ohne Zustimmung kannst du JYRY AI nicht nutzen. "
    "Bitte lies die Hinweise erneut und bestätige sie unten."
)

# Paid-plan consent — shown once before the first Paddle checkout.
PAID_CONSENT_WARNING = (
    "💳 *Abo-Bedingungen*\n\n"
    "Bevor du dein Abo abschließt, bestätige bitte:\n\n"
    "1. *Abwicklung über Paddle*: Paddle ist der Merchant of Record, "
    "übernimmt die Mehrwertsteuer und stellt den Beleg aus. Die Buchung "
    "erscheint auf deiner Karte als Paddle-Transaktion.\n"
    "2. *Automatische Verlängerung*: Plus monatlich, Pro alle 3 Monate, "
    "Max alle 6 Monate. Du wirst 3 Tage vor jeder Verlängerung per "
    "Telegram erinnert.\n"
    "3. *Verzicht auf Rücktritt und Rückerstattung*: Die Dienstleistung "
    "beginnt sofort nach Zahlung und verbraucht laufend Ressourcen "
    "(E-Mail-Versand, Server, SMTP-Kontingente). Mit deiner Zustimmung "
    "verzichtest du ausdrücklich auf das Recht zum Rücktritt und auf "
    "jede Rückerstattung der bereits gezahlten Laufzeit.\n"
    "4. *Statt Kündigung: Upgrade möglich* — du kannst jederzeit auf "
    "einen höheren Tarif wechseln. Paddle berechnet anteilig den "
    "Differenzbetrag nach bisheriger Nutzung und bucht ihn sofort von "
    "deiner hinterlegten Karte ab.\n"
    "5. *Beendigung des Abos*: Wenn du nicht upgraden möchtest, kannst "
    "du die automatische Verlängerung jederzeit deaktivieren. Dein "
    "Tarif bleibt dann bis zum Ende der bereits bezahlten Laufzeit "
    "aktiv und wird danach nicht erneut abgebucht.\n\n"
    "Bestätige unten, um zur Bezahlung weiterzuleiten."
)
PAID_CONSENT_BUTTON_ACCEPT = "✅ Zustimmen und zur Bezahlung"
PAID_CONSENT_BUTTON_DECLINE = "❌ Abbrechen"

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
MENU_TEMPLATES = "📝 Vorlagen entdecken"
TEMPLATES_TITLE = (
    "📝 *Vorlagen entdecken*\n\n"
    "Wähle eine vorgefertigte Bewerbungstext-Vorlage. Du kannst sie direkt "
    "übernehmen oder später unter *Bewerbungstext bearbeiten* anpassen."
)
TEMPLATES_NEED_PRO = (
    "🔒 *Vorlagen entdecken* ist nur in den Tarifen *Pro* und *Max* verfügbar.\n\n"
    "Upgrade dein Abo, um auf alle vorgefertigten Bewerbungstexte zuzugreifen."
)
TEMPLATES_NO_SPECIALTIES = (
    "⚠️ Du hast noch keinen Beruf ausgewählt. Wähle erst deine Berufe aus, "
    "dann zeigen wir dir die passenden Vorlagen."
)
TEMPLATE_PREVIEW = (
    "📄 *Vorlage: {keyword}*\n\n"
    "```\n{body}\n```\n\n"
    "Möchtest du diese Vorlage übernehmen?"
)
TEMPLATE_APPLIED = (
    "✅ *Vorlage übernommen!*\n\n"
    "Du kannst sie jederzeit unter *Bewerbungstext bearbeiten* anpassen."
)
TEMPLATE_BACK_TO_LIST = "🔙 Andere Vorlage"
TEMPLATE_APPLY_LABEL = "✅ Übernehmen"

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
    "Paddle kündigen."
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
    "PLANS_TITLE_ACTIVE",
    "PLAN_ALREADY_MAX",
    "PLAN_UPGRADE_CONFIRM",
    "PLAN_UPGRADE_BUTTON",
    "PLAN_UPGRADE_SUCCESS",
    "PLAN_UPGRADE_FAILED",
    "PLAN_UPGRADE_PREFIX",
    "PLAN_CANCEL_LABEL",
    "PLAN_RETENTION_OFFER",
    "PLAN_RETENTION_UPGRADE_BUTTON",
    "PLAN_RETENTION_PROCEED_BUTTON",
    "PLAN_CANCEL_CONFIRM",
    "PLAN_CANCEL_CONFIRM_BUTTON",
    "PLAN_CANCEL_SUCCESS",
    "PLAN_CANCEL_FAILED",
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
    "MENU_TEMPLATES",
    "TEMPLATES_TITLE",
    "TEMPLATES_NEED_PRO",
    "TEMPLATES_NO_SPECIALTIES",
    "TEMPLATE_PREVIEW",
    "TEMPLATE_APPLIED",
    "TEMPLATE_BACK_TO_LIST",
    "TEMPLATE_APPLY_LABEL",
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
