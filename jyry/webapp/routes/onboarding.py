"""Web onboarding / setup: specialties, states, email template, attachments.

Mirrors the Telegram bot's onboarding so a user who signed up on the web can
complete everything the sender needs (see ``dispatch_one`` readiness checks)
without ever opening Telegram. Attachments are stored on the local filesystem
under ``settings.upload_dir`` and resolved by the dispatcher at send time.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.bot import repos
from jyry.config import Settings
from jyry.constants import (
    PLAN_MAX_SPECIALTIES,
    PLAN_MAX_STATES,
    SPECIALTIES,
    SPECIALTY_KEYWORDS,
    STATE_CODES,
    STATES,
)
from jyry.db.models import User
from jyry.webapp.deps import get_app_settings, get_current_user, get_db
from jyry.webapp.schemas import (
    AttachmentOut,
    OnboardingOut,
    SelectionPut,
    SpecialtyRef,
    StateRef,
    TemplatePut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

_MAX_ATTACHMENTS = 8
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB, same as the bot


def _attachments_out(user: User) -> list[AttachmentOut]:
    draft = user.email_draft
    metas = (draft.attachments_meta if draft else None) or []
    out: list[AttachmentOut] = []
    for i, meta in enumerate(metas):
        out.append(
            AttachmentOut(
                index=i,
                filename=meta.get("filename") or "attachment.pdf",
                size=int(meta.get("size") or 0),
                mime=meta.get("mime"),
                source="local" if meta.get("local_path") else "telegram",
            )
        )
    return out


def _is_ready(user: User) -> bool:
    draft = user.email_draft
    return bool(
        user.gmail_address
        and user.gmail_app_password_enc is not None
        and draft is not None
        and (draft.subject_template or "").strip()
        and user.specialties
        and user.states
    )


def _build_onboarding_out(user: User) -> OnboardingOut:
    draft = user.email_draft
    plan = repos.plan_value(user)
    return OnboardingOut(
        specialties=[s.specialty_keyword for s in user.specialties],
        states=[s.state_code for s in user.states],
        subject_template=(draft.subject_template if draft else "") or "",
        body_template=(draft.body_template if draft else "") or "",
        attachments=_attachments_out(user),
        all_specialties=[
            SpecialtyRef(keyword=kw, label_de=kw, label_ar=ar)
            for kw, ar in SPECIALTIES
        ],
        all_states=[
            StateRef(code=code, label_de=de, label_ar=ar)
            for code, de, ar in STATES
        ],
        max_specialties=PLAN_MAX_SPECIALTIES.get(plan),
        max_states=PLAN_MAX_STATES.get(plan),
        has_app_password=user.gmail_app_password_enc is not None,
        ready=_is_ready(user),
        onboarding_complete=user.onboarding_complete,
        plan=plan,
    )


@router.get("", response_model=OnboardingOut)
async def get_onboarding(user: User = Depends(get_current_user)) -> OnboardingOut:
    return _build_onboarding_out(user)


@router.put("/selection")
async def put_selection(
    body: SelectionPut,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # De-dupe while preserving order, then validate against the static catalog.
    specialties = list(dict.fromkeys(body.specialties))
    states = list(dict.fromkeys(body.states))

    bad_spec = [s for s in specialties if s not in SPECIALTY_KEYWORDS]
    if bad_spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown specialties: {bad_spec}",
        )
    bad_state = [s for s in states if s not in STATE_CODES]
    if bad_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown states: {bad_state}",
        )

    plan = repos.plan_value(user)
    max_spec = PLAN_MAX_SPECIALTIES.get(plan)
    max_states = PLAN_MAX_STATES.get(plan)
    if max_spec is not None and len(specialties) > max_spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dein Tarif erlaubt höchstens {max_spec} Fachrichtung(en).",
        )
    if max_states is not None and len(states) > max_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dein Tarif erlaubt höchstens {max_states} Bundesland/Bundesländer.",
        )

    await repos.replace_specialties(session, user.id, specialties)
    await repos.replace_states(session, user.id, states)
    await session.commit()
    return {"ok": True}


@router.put("/template")
async def put_template(
    body: TemplatePut,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    subject = body.subject_template.strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Betreff darf nicht leer sein.",
        )
    await repos.upsert_draft(
        session,
        user.id,
        subject_template=subject,
        body_template=body.body_template,
    )
    await session.commit()
    return {"ok": True}


@router.post("/attachments")
async def upload_attachment(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    existing = (user.email_draft.attachments_meta if user.email_draft else None) or []
    if len(existing) >= _MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximal {_MAX_ATTACHMENTS} Anhänge.",
        )

    filename = (file.filename or "").strip()
    is_pdf = file.content_type == "application/pdf" or filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur PDF-Dateien sind erlaubt.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Datei ist leer."
        )
    if len(content) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datei ist größer als 10 MB.",
        )

    user_dir = Path(settings.upload_dir) / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored = user_dir / f"{uuid.uuid4().hex}.pdf"
    stored.write_bytes(content)

    safe_name = Path(filename).name or "Dokument.pdf"
    await repos.append_local_attachment(
        session,
        user.id,
        filename=safe_name,
        local_path=str(stored),
        mime="application/pdf",
        size=len(content),
    )
    await session.commit()
    return {"ok": True}


@router.delete("/attachments/{index}")
async def delete_attachment(
    index: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    draft = user.email_draft
    metas = (draft.attachments_meta if draft else None) or []
    if not (0 <= index < len(metas)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Anhang nicht gefunden."
        )
    # Best-effort: delete the backing file for web uploads before dropping the row.
    local_path = metas[index].get("local_path")
    if local_path:
        try:
            Path(local_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("could not unlink upload %s", local_path)

    await repos.remove_attachment_at(session, user.id, index)
    await session.commit()
    return {"ok": True}


@router.post("/complete")
async def complete(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if not _is_ready(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup ist noch nicht vollständig.",
        )
    await repos.complete_onboarding(session, user.id)
    await session.commit()
    return {"ok": True, "onboarding_complete": True}
