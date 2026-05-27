"""Admin-only endpoints. All gated by get_current_admin."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyry.bot import repos
from jyry.db.enums import ApplicationStatus, Plan, SubscriptionStatus
from jyry.db.models import Application, Subscription, User
from jyry.webapp.deps import get_current_admin, get_db
from jyry.webapp.schemas import AdminStats, AdminUserRow, AdminUsersPage

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)]
)


def _plan_value(user: User) -> str:
    sub = user.subscription
    if sub is None or sub.plan is None:
        return "free"
    return sub.plan.value if isinstance(sub.plan, Plan) else str(sub.plan)


@router.get("/stats", response_model=AdminStats)
async def stats(session: AsyncSession = Depends(get_db)) -> AdminStats:
    users_total = (await session.execute(select(func.count(User.id)))).scalar_one()
    users_active = (
        await session.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one()

    by_plan: dict[str, int] = {"free": 0, "plus": 0, "pro": 0, "max": 0}
    rows = await session.execute(
        select(Subscription.plan, func.count(Subscription.id))
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .group_by(Subscription.plan)
    )
    for plan, count in rows.all():
        key = plan.value if isinstance(plan, Plan) else str(plan)
        by_plan[key] = count

    sent_today = (
        await session.execute(
            select(func.coalesce(func.sum(Subscription.emails_sent_today), 0))
        )
    ).scalar_one()
    sent_total = (
        await session.execute(
            select(func.count(Application.id)).where(
                Application.status == ApplicationStatus.SENT
            )
        )
    ).scalar_one()

    return AdminStats(
        users_total=int(users_total),
        users_active=int(users_active),
        users_by_plan=by_plan,
        emails_sent_today=int(sent_today),
        emails_sent_total=int(sent_total),
    )


@router.get("/users", response_model=AdminUsersPage)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    q: str | None = Query(default=None, description="search by email / full_name"),
    session: AsyncSession = Depends(get_db),
) -> AdminUsersPage:
    stmt = select(User).options(selectinload(User.subscription))
    count_stmt = select(func.count(User.id))
    if q:
        like = f"%{q.lower()}%"
        clause = User.email.ilike(like) | User.full_name.ilike(like)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(User.created_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .scalars()
        .all()
    )

    user_ids = [r.id for r in rows]
    sent_total_map: dict[int, int] = {}
    if user_ids:
        per_user = await session.execute(
            select(Application.user_id, func.count(Application.id))
            .where(
                Application.user_id.in_(user_ids),
                Application.status == ApplicationStatus.SENT,
            )
            .group_by(Application.user_id)
        )
        for uid, count in per_user.all():
            sent_total_map[uid] = int(count)

    items = [
        AdminUserRow(
            id=r.id,
            email=r.email,
            full_name=r.full_name,
            telegram_id=r.telegram_id,
            plan=_plan_value(r),
            is_active=r.is_active,
            is_admin=r.is_admin,
            onboarding_complete=r.onboarding_complete,
            notification_mode=r.notification_mode,
            created_at=r.created_at,
            last_seen_at=r.updated_at,
            emails_sent_today=(r.subscription.emails_sent_today if r.subscription else 0),
            emails_sent_total=sent_total_map.get(r.id, 0),
        )
        for r in rows
    ]
    return AdminUsersPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/users/{user_id}/grant-trial", status_code=204)
async def grant_trial(
    user_id: int, session: AsyncSession = Depends(get_db)
) -> None:
    """Force-grant a fresh 3-day Free trial (debug / support tool)."""
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user.trial_started_at = None
    if user.subscription is not None:
        await session.delete(user.subscription)
        await session.flush()
    await repos.grant_free_trial(session, user_id)
    await session.commit()


@router.post("/users/{user_id}/toggle-active", status_code=204)
async def toggle_active(
    user_id: int, session: AsyncSession = Depends(get_db)
) -> None:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user.is_active = not user.is_active
    await session.commit()


@router.post("/users/{user_id}/promote", status_code=204)
async def promote_admin(
    user_id: int, session: AsyncSession = Depends(get_db)
) -> None:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user.is_admin = True
    await session.commit()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)) -> dict:
    """Quick liveness probe — useful from the admin UI."""
    now = datetime.now(tz=UTC)
    recent_sends = (
        await session.execute(
            select(func.count(Application.id)).where(
                Application.status == ApplicationStatus.SENT,
                Application.sent_at > now - timedelta(hours=1),
            )
        )
    ).scalar_one()
    return {
        "ok": True,
        "now": now.isoformat(),
        "sends_last_hour": int(recent_sends),
    }
