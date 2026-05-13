"""Static reference data: supported specialties and Bundesländer."""

from __future__ import annotations

from typing import Final

# 13 Ausbildung specialties JYRY AI targets. The German keyword is the value
# we send to the Bundesagentur API; the Arabic label is what we show in the
# Telegram UI.
SPECIALTIES: Final[tuple[tuple[str, str], ...]] = (
    ("Pflegefachmann", "تمريض (متخصص)"),
    ("Krankenpflegehelfer", "مساعد تمريض"),
    ("Notfallsanitäter", "مسعف طوارئ"),
    ("Mechatroniker", "ميكاترونيكس"),
    ("Fachinformatiker für Anwendungsentwicklung", "تطوير تطبيقات (IT)"),
    ("Fachinformatiker für Systemintegration", "تكامل أنظمة (IT)"),
    ("Kaufmann", "تاجر / موظف تجاري"),
    ("Bankkaufmann", "موظف بنك"),
    ("Hotelfachmann", "فندقة"),
    ("Verkäufer", "بائع"),
    ("Elektroniker", "كهربائي إلكترونيات"),
    ("Bäcker", "خباز"),
    ("Koch", "طبّاخ"),
)

SPECIALTY_KEYWORDS: Final[tuple[str, ...]] = tuple(k for k, _ in SPECIALTIES)
SPECIALTY_LABELS_AR: Final[dict[str, str]] = dict(SPECIALTIES)

# 16 German Bundesländer (state code -> (DE, AR)).
STATES: Final[tuple[tuple[str, str, str], ...]] = (
    ("BW", "Baden-Württemberg", "بادن-فورتمبيرغ"),
    ("BY", "Bayern", "بافاريا"),
    ("BE", "Berlin", "برلين"),
    ("BB", "Brandenburg", "براندنبورغ"),
    ("HB", "Bremen", "بريمن"),
    ("HH", "Hamburg", "هامبورغ"),
    ("HE", "Hessen", "هيسن"),
    ("MV", "Mecklenburg-Vorpommern", "مكلنبورغ-فوربومرن"),
    ("NI", "Niedersachsen", "ساكسونيا السفلى"),
    ("NW", "Nordrhein-Westfalen", "شمال الراين-ويستفاليا"),
    ("RP", "Rheinland-Pfalz", "راينلاند-بفالتس"),
    ("SL", "Saarland", "زارلاند"),
    ("SN", "Sachsen", "ساكسونيا"),
    ("ST", "Sachsen-Anhalt", "ساكسونيا-أنهالت"),
    ("SH", "Schleswig-Holstein", "شليسفيغ-هولشتاين"),
    ("TH", "Thüringen", "تورنغن"),
)

STATE_CODES: Final[tuple[str, ...]] = tuple(code for code, _, _ in STATES)
STATE_LABELS_DE: Final[dict[str, str]] = {code: de for code, de, _ in STATES}
STATE_LABELS_AR: Final[dict[str, str]] = {code: ar for code, _, ar in STATES}


# Plan -> daily quota of emails the sender will dispatch.
PLAN_DAILY_QUOTA: Final[dict[str, int]] = {
    "free": 5,
    "plus": 30,
    "pro": 100,
    "max": 100,
}

# Plan -> display price (German formatting, used in renewal reminders).
PLAN_PRICES: Final[dict[str, str]] = {
    "plus": "14,99",
    "pro": "29,99",
    "max": "99,00",
}

# Plan -> max number of specialties the user may pick (None = all).
PLAN_MAX_SPECIALTIES: Final[dict[str, int | None]] = {
    "free": 1,
    "plus": 3,
    "pro": None,
    "max": None,
}

# Plan -> max number of Bundesländer the user may pick (None = all).
PLAN_MAX_STATES: Final[dict[str, int | None]] = {
    "free": 1,
    "plus": 6,
    "pro": None,
    "max": None,
}
