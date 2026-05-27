"""Application history. Company name is intentionally NOT exposed — privacy
policy carries over from the bot's notification design.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.db.enums import ApplicationStatus
from jyry.db.models import Application, User
from jyry.webapp.deps import get_current_user, get_db
from jyry.webapp.schemas import ApplicationOut, ApplicationsPage

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=ApplicationsPage)
async def list_applications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApplicationsPage:
    stmt = select(Application).where(Application.user_id == user.id)
    count_stmt = select(func.count(Application.id)).where(
        Application.user_id == user.id
    )
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
        count_stmt = count_stmt.where(Application.status == status_filter)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Application.queued_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .scalars()
        .all()
    )

    items = [
        ApplicationOut(
            id=r.id,
            job_title=r.job_title,
            sent_at=r.sent_at,
            status=(
                r.status.value if isinstance(r.status, ApplicationStatus) else str(r.status)
            ),
            error_message=r.error_message,
            created_at=r.queued_at,
        )
        for r in rows
    ]
    return ApplicationsPage(items=items, total=total, page=page, page_size=page_size)
