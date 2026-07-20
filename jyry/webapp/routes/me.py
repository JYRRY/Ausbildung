"""GET /api/me — the logged-in user's profile, sub status, and counters."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from jyry.bot import repos
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.enums import SubscriptionStatus
from jyry.db.models import User
from jyry.webapp.deps import get_current_user
from jyry.webapp.schemas import MeOut, SubscriptionOut

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    sub = user.subscription
    sub_out = None
    if sub is not None:
        plan_value = repos.plan_value(user)
        quota = PLAN_DAILY_QUOTA.get(plan_value, PLAN_DAILY_QUOTA["free"])
        sub_out = SubscriptionOut(
            plan=plan_value,
            status=(
                sub.status.value
                if isinstance(sub.status, SubscriptionStatus)
                else str(sub.status)
            ),
            started_at=sub.started_at,
            expires_at=sub.expires_at,
            emails_sent_today=sub.emails_sent_today or 0,
            daily_quota=quota,
            auto_renew=bool(sub.paddle_subscription_id),
        )

    return MeOut(
        id=user.id,
        email=user.email,
        google_picture=user.google_picture,
        full_name=user.full_name,
        postal_street=user.postal_street,
        postal_plz_city=user.postal_plz_city,
        phone=user.phone,
        gmail_address=user.gmail_address,
        has_app_password=user.gmail_app_password_enc is not None,
        telegram_id=user.telegram_id,
        telegram_linked=user.telegram_id is not None,
        is_admin=user.is_admin,
        is_active=user.is_active,
        onboarding_complete=user.onboarding_complete,
        notification_mode=user.notification_mode,
        accepted_terms_at=user.accepted_terms_at,
        accepted_paid_terms_at=user.accepted_paid_terms_at,
        trial_started_at=user.trial_started_at,
        subscription=sub_out,
    )
