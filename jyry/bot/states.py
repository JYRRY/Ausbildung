"""ConversationHandler state IDs.

Kept as an ``IntEnum`` so PTB's state machine compares them as plain ints
while we still get descriptive names in tracebacks.
"""

from __future__ import annotations

import enum


class OnboardingState(enum.IntEnum):
    ASK_NAME = 1
    ASK_GMAIL_CONSENT = 2
    ASK_GMAIL_ADDRESS = 3
    ASK_APP_PASSWORD = 4
    ASK_SPECIALTIES = 5
    ASK_STATES = 6
    ASK_EMAIL_BODY = 7
    ASK_ATTACHMENTS = 8
    CONFIRM = 9
    DONE = 10
